"""Slice 1 (latency): the turn-latency runner.

Drives real customer turns through the real chat surface - ``POST /api/chat``,
the same route, controller, and SSE shape the browser hits - with one model
pinned per run, and writes one JSON file per model x tenant under the evidence
folder.

**Why in-process.** The per-turn record is emitted by the chat controller as a
single structured log line on the ``app.latency`` logger (see
``app/observability/turn_record.py``). Running the app through httpx's
``ASGITransport`` in this same process lets the runner attach a logging handler
and tap exactly that line: no cross-process log plumbing, and no way for a turn
served elsewhere to land in this run's evidence. The route, controller, graph,
retrieval, and SSE framing are all the real ones.

**Model pinning.** ``docker compose run -e`` pins a *container*; the runner must
pin the *process* it drives. It writes ``LLM_PROVIDER`` / ``LLM_BASE_URL`` /
``LLM_API_KEY`` / ``LLM_MODEL`` and, in the default ``single`` mode, empties
both other tiers' model names, then clears the settings cache, so the app
builds exactly one provider leg. ``--legs configured`` leaves the fallback and
failover tiers as the container's ``.env`` configured them, so the production
race runs unchanged. Each
turn's ``usage_models`` carries the model the provider says it **served** (read
from the response body, see ``app/llm/openai_base.py``), not the id that was
requested; ``model_match`` is true only when every reported model equals the
pinned ``api_model`` and at least one call reported usage, so a turn answered by
a different model is ``model_match: false`` and is never averaged in.

Usage::

    python -m evals.latency_run                      # smoke: first model, first tenant, one turn
    python -m evals.latency_run --models all --tenants all --turns 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx

from app.observability.turn_record import LATENCY_LOGGER_NAME
from app.shared.config import get_settings

DEFAULT_CONFIG = Path(__file__).with_name("latency_config.json")
DEFAULT_OUT = Path("/evidence/data")
PROVIDER_HTTP_TIMEOUT_S = 30.0
TURN_TIMEOUT_S = 180.0

# Emptied on every pin so exactly one leg is configured for the run.
_DISABLED_LEG_VARS = (
    "LLM_FALLBACK_MODEL",
    "LLM_FALLBACK_API_KEY",
    "LLM_FAILOVER_MODEL",
    "LLM_FAILOVER_API_KEY",
)


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _commit_sha() -> str:
    """The measured commit, handed in by the Makefile: git is not reachable
    inside the container, which mounts only ./backend."""
    return os.environ.get("LATENCY_COMMIT", "")


def _make_command(args: argparse.Namespace) -> str:
    """The `make latency` invocation that reproduces this run, for the evidence."""
    parts = ["make latency"]
    if args.models:
        parts.append(f"LATENCY_MODELS={args.models}")
    if args.tenants:
        parts.append(f"LATENCY_TENANTS={args.tenants}")
    if args.turns != 1:
        parts.append(f"LATENCY_TURNS={args.turns}")
    if args.conversation != "fresh":
        parts.append(f"LATENCY_CONVERSATION={args.conversation}")
    if args.legs != "single":
        parts.append(f"LATENCY_LEGS={args.legs}")
    return " ".join(parts)


def _slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value).strip("-").lower()


class _RecordHandler(logging.Handler):
    """Collects the ``latency_turn`` payload off every record on ``app.latency``."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[dict[str, Any]] = []

    def emit(self, record: logging.LogRecord) -> None:
        payload = getattr(record, "latency_turn", None)
        if isinstance(payload, dict):
            self.records.append(payload)


def _load_config(path: Path) -> dict[str, Any]:
    with path.open() as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def _select(items: list[dict[str, Any]], selector: str | None, key: str) -> list[dict[str, Any]]:
    """The selected config rows: default the first, ``all`` for every row, or a
    comma-separated list of keys."""
    if selector is None:
        return items[:1]
    if selector == "all":
        return items
    wanted = {s.strip() for s in selector.split(",") if s.strip()}
    chosen = [item for item in items if item.get(key) in wanted]
    missing = wanted - {item.get(key) for item in chosen}
    if missing:
        raise SystemExit(f"unknown {key}: {', '.join(sorted(missing))}")
    return chosen


async def _fetch_provider_models(
    http: httpx.AsyncClient, url: str, key: str
) -> list[dict[str, Any]]:
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    resp = await http.get(url, headers=headers)
    resp.raise_for_status()
    raw: Any = resp.json()
    models = raw.get("data") if isinstance(raw, dict) else None
    return models if isinstance(models, list) else []


def _find_model(models: list[dict[str, Any]], api_model: str) -> dict[str, Any] | None:
    for entry in models:
        if isinstance(entry, dict) and entry.get("id") == api_model:
            return entry
    return None


def _embedder_config() -> dict[str, Any]:
    """The effective embedder, recorded so a hybrid tenant's ``embed_ms`` can be
    attributed to a concrete model rather than an ambient setting."""
    settings = get_settings()
    if settings.embedder == "local":
        model = settings.local_embed_model
    elif settings.embedder == "google":
        model = settings.google_embed_model
    else:
        model = ""
    return {"provider": settings.embedder, "model": model}


async def _probe_provider(http: httpx.AsyncClient, model: dict[str, Any]) -> str | None:
    """A minimal direct completion against the provider, for a probe-tier model.

    The Zen free tier rejects any non-OpenCode client at the endpoint itself,
    and the app's chat surface hides that: the controller turns a provider fault
    into a graceful handoff, so the SSE carries no error text. Probing the
    endpoint directly records the exact refusal. Returns ``None`` when the
    provider answered, or the error body/exception text otherwise.
    """
    key = os.environ.get(str(model["key_env"]), "")
    url = f"{str(model['base_url']).rstrip('/')}/chat/completions"
    try:
        resp = await http.post(
            url,
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model["api_model"],
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            },
        )
    except httpx.HTTPError as exc:
        return f"{type(exc).__name__}: {exc}"
    if resp.status_code >= 400:
        return f"HTTP {resp.status_code}: {resp.text[:500]}"
    return None


def _pin_model(model: dict[str, Any], legs: str = "single") -> None:
    """Pin the primary leg. ``single`` also blanks the rest of the chain;
    ``configured`` leaves the container's .env fallback/failover intact."""
    key = os.environ.get(str(model["key_env"]), "")
    if not key:
        raise SystemExit(f"{model['key_env']} is unset")
    os.environ["LLM_PROVIDER"] = "openai_compat"
    os.environ["LLM_BASE_URL"] = str(model["base_url"])
    os.environ["LLM_API_KEY"] = key
    os.environ["LLM_MODEL"] = str(model["api_model"])
    if legs == "single":
        for var in _DISABLED_LEG_VARS:
            os.environ[var] = ""
    get_settings.cache_clear()


def _legs_config() -> dict[str, Any]:
    """The non-secret identity of the configured fallback/failover legs."""
    settings = get_settings()
    return {
        "fallback": {
            "model": settings.llm_fallback_model,
            "base_url": settings.llm_fallback_base_url,
        },
        "failover": {
            "model": settings.llm_failover_model,
            "base_url": settings.llm_failover_base_url,
        },
    }


async def _drive_turn(
    client: httpx.AsyncClient,
    *,
    slug: str,
    message: str,
    conversation_id: str | None,
) -> tuple[str | None, list[str], str | None]:
    """One real turn. Returns (conversation_id, event types, error)."""
    body: dict[str, Any] = {"slug": slug, "message": message}
    if conversation_id is not None:
        body["conversation_id"] = conversation_id
    resp = await client.post("/api/chat", json=body)
    if resp.status_code != 200:
        return None, [], f"HTTP {resp.status_code}: {resp.text[:200]}"

    seen: str | None = None
    event_types: list[str] = []
    for line in resp.text.splitlines():
        if not line.startswith("data: "):
            continue
        try:
            event = json.loads(line[len("data: ") :])
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        event_types.append(str(event.get("type")))
        if event.get("type") == "conversation":
            seen = str(event.get("conversation_id"))
    return seen, event_types, None


async def _run_model_tenant(
    client: httpx.AsyncClient,
    http: httpx.AsyncClient,
    *,
    model: dict[str, Any],
    tenant: dict[str, Any],
    turns: int,
    command: str,
    handler: _RecordHandler,
    conversation: str = "fresh",
    legs_mode: str = "single",
    legs_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider_models = await _fetch_provider_models(
        http, str(model["models_url"]), os.environ.get(str(model["key_env"]), "")
    )
    fetched_at = _utc_now()
    provider_ids = sorted(
        str(m["id"]) for m in provider_models if isinstance(m, dict) and m.get("id")
    )
    entry = _find_model(provider_models, str(model["api_model"]))
    messages = [str(m) for m in tenant.get("messages", [])] or [str(tenant.get("message", ""))]
    result: dict[str, Any] = {
        "model": {k: model.get(k) for k in ("label", "route", "base_url", "api_model", "tier")},
        "tenant": tenant["slug"],
        "messages": messages,
        "expected_path": tenant.get("expected_path"),
        "expected_llm_calls": tenant.get("expected_llm_calls"),
        "provider_models_fetched_at": fetched_at,
        "provider_model_present": entry is not None,
        "provider_model_count": len(provider_ids),
        "provider_id_form": model.get("provider_id_form"),
        "provider_pricing": entry.get("pricing") if entry else None,
        "embedder": _embedder_config(),
        "command": command,
        "conversation_mode": conversation,
        "legs_mode": legs_mode,
        "commit": _commit_sha(),
        "generated_at": _utc_now(),
        "turns": [],
    }
    if legs_config is not None:
        result["legs_config"] = legs_config
    if entry is None:
        # Record the exact catalogue so the absence is checkable from the
        # artifact, not just asserted.
        result["provider_model_ids"] = provider_ids
        result["skipped"] = (
            f"{model['api_model']} absent from {model['models_url']} at {fetched_at} "
            f"(catalogue carried {len(provider_ids)} ids)"
        )
        return result
    if model.get("tier") == "probe":
        probe_error = await _probe_provider(http, model)
        if probe_error is not None:
            result["provider_model_ids"] = provider_ids
            result["provider_probe_error"] = probe_error
            result["skipped"] = (
                f"provider refused a probe call to {model['api_model']}: {probe_error}"
            )
            return result

    # ``fresh`` measures the fixed message set independently: each turn is its
    # own conversation, so a growing transcript does not confound the run-to-run
    # comparison. ``reuse`` keeps the id the previous turn opened, so the
    # transcript grows the way it does for a customer sending rapid messages.
    # Turns cycle through the messages when fewer messages than turns are given.
    current_id: str | None = None
    for turn_index in range(turns):
        message = messages[turn_index % len(messages)]
        handler.records.clear()
        conversation_id, event_types, error = await _drive_turn(
            client,
            slug=str(tenant["slug"]),
            message=message,
            conversation_id=current_id if conversation == "reuse" else None,
        )
        if error is not None:
            result["turns"].append({"message": message, "error": error})
            break
        if conversation == "reuse":
            current_id = conversation_id
        matches = [r for r in handler.records if r.get("conversation_id") == conversation_id]
        if not matches:
            result["turns"].append(
                {
                    "message": message,
                    "conversation_id": conversation_id,
                    "error": "no latency record emitted for this turn",
                    "event_types": event_types,
                }
            )
            continue
        for record in matches:
            usage_models = [str(m) for m in record.get("usage_models", [])]
            result["turns"].append(
                {
                    "message": message,
                    "conversation_id": record.get("conversation_id"),
                    "usage_models": usage_models,
                    # True only when every served model a call reported equals
                    # the pinned id AND at least one call reported usage.
                    # ``usage_models`` now carries the served model (from the
                    # provider response), so this is a real identity check, not
                    # a comparison of the id we asked for against itself.
                    "model_match": bool(usage_models)
                    and set(usage_models) == {str(model["api_model"])},
                    "event_types": event_types,
                    "record": record.get("record"),
                }
            )
    return result


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def _print_turn(model_label: str, tenant: str, index: int, turn: dict[str, Any]) -> None:
    if turn.get("error") is not None:
        print(f"  {model_label} x {tenant} turn {index}: ERROR {turn['error']}")
        return
    record = turn.get("record") or {}
    print(
        f"  {model_label} x {tenant} turn {index}: "
        f"total_ms={record.get('total_ms')} path={record.get('path')} "
        f"route={record.get('route')} calls={record.get('llm_call_count')} "
        f"leg={record.get('leg')} failover={record.get('failover_engaged')} "
        f"model_match={turn.get('model_match')}"
    )


async def run(args: argparse.Namespace) -> int:
    from app.main import app

    config = _load_config(Path(args.config))
    models = _select(list(config["models"]), args.models, "label")
    tenants = _select(list(config["corpus"]), args.tenants, "slug")
    out_dir = Path(args.out)
    command = _make_command(args)

    handler = _RecordHandler()
    latency_logger = logging.getLogger(LATENCY_LOGGER_NAME)
    latency_logger.setLevel(logging.INFO)
    latency_logger.addHandler(handler)

    written: list[Path] = []
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with (
            httpx.AsyncClient(
                transport=transport, base_url="http://latency", timeout=TURN_TIMEOUT_S
            ) as client,
            httpx.AsyncClient(timeout=PROVIDER_HTTP_TIMEOUT_S) as http,
        ):
            for model in models:
                try:
                    _pin_model(model, legs=args.legs)
                except SystemExit as exc:
                    path = out_dir / f"{_slugify(str(model['label']))}__skipped.json"
                    _write(
                        path,
                        {
                            "model": model,
                            "skipped": str(exc),
                            "legs_mode": args.legs,
                            "command": command,
                            "commit": _commit_sha(),
                            "generated_at": _utc_now(),
                        },
                    )
                    written.append(path)
                    print(f"SKIP {model['label']}: {exc}")
                    continue
                legs_config = _legs_config() if args.legs == "configured" else None
                for tenant in tenants:
                    result = await _run_model_tenant(
                        client,
                        http,
                        model=model,
                        tenant=tenant,
                        turns=args.turns,
                        command=command,
                        handler=handler,
                        conversation=args.conversation,
                        legs_mode=args.legs,
                        legs_config=legs_config,
                    )
                    path = out_dir / f"{_slugify(str(model['label']))}__{tenant['slug']}.json"
                    _write(path, result)
                    written.append(path)
                    if result.get("skipped") is not None:
                        print(f"SKIP {model['label']} x {tenant['slug']}: {result['skipped']}")
                        continue
                    for index, turn in enumerate(result["turns"], start=1):
                        _print_turn(str(model["label"]), str(tenant["slug"]), index, turn)

    print(f"\nwrote {len(written)} file(s):")
    for path in written:
        print(f"  {path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument(
        "--models", default=None, help="comma-separated model labels, or 'all' (default: first)"
    )
    parser.add_argument(
        "--tenants", default=None, help="comma-separated tenant slugs, or 'all' (default: first)"
    )
    parser.add_argument(
        "--turns",
        type=int,
        default=1,
        help="turns per tenant; with --conversation reuse they share one conversation",
    )
    parser.add_argument(
        "--conversation",
        choices=("fresh", "reuse"),
        default="fresh",
        help="fresh opens a new conversation each turn; reuse keeps turn 1's (default: fresh)",
    )
    parser.add_argument(
        "--legs",
        choices=("single", "configured"),
        default="single",
        help="single blanks the fallback/failover legs; configured uses the .env chain",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="evidence output directory")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="model and corpus config")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
