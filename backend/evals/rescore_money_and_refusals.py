"""Post-hoc re-score of two false positives in one benchmark artifact.

Two metrics in the 2026-10 artifacts were wrong for reasons the artifact can
still be corrected for:

- **Money.** ``rec-refurb-phone-01`` quoted the tenant catalog's own four
  refurbished-phone prices. The trajectory scorer only received the engine
  quote, recommendation provenance, and retrieved chunks, so real catalog rows
  looked unsourced. The benchmark now hands the catalog to the scorer; this
  tool removes the old violations that a catalog price explains.
- **Refusal.** The strict metric requires the exact refusal constant, so
  correct refusals in the model's own words scored 0. The generation suite now
  records a semantic judge beside the strict metric; this tool adds that
  verdict to the 12 negative cases.

Every other case field and every other criterion is preserved. The aggregate
and verdict are rebuilt with the benchmark's own ``aggregate_cases`` and
``_finish_artifact`` helpers, so a re-scored artifact is judged exactly as a
fresh run judges it. The artifact is snapshotted to ``.bak`` before an atomic
write, and secrets are redacted first.

Usage::

    python -m evals.rescore_money_and_refusals --artifact /tmp/a.json --dry-run
    python -m evals.rescore_money_and_refusals --artifact /tmp/a.json
    python -m evals.rescore_money_and_refusals --artifact /tmp/a.json --out /tmp/fixed.json
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import json
import os
import shutil
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from app.pricing.validation_gate import extract_monetary_figures
from app.shared import db
from evals.model_benchmark import (
    BOOTSTRAP_SEED,
    DEFAULT_CONFIG,
    MeteredProvider,
    _finish_artifact,
    _redact_tree,
    _secrets,
    aggregate_cases,
    build_provider,
    load_config,
    offering_price_cents,
    score_semantic_refusal,
    tenant_id_for,
)
from evals.rescore_citations import options_from_command
from seeds.seed_sababa2 import SLUG as SABABA2_SLUG
from seeds.seed_tenant1_phoneshop import SLUG as TENANT1_SLUG

MONEY_PREFIX = "unsourced monetary figure in draft: "
_TENANT_SLUGS = {"tenant1": TENANT1_SLUG, "sababa2": SABABA2_SLUG}
_SUITES = ("trajectory", "generation")


class RescoreError(RuntimeError):
    """The artifact cannot be re-scored safely."""


@dataclass(frozen=True)
class MoneyChange:
    case_id: str
    repeat: Any
    before: int
    after: int
    cleared: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RefusalChange:
    case_id: str
    repeat: Any
    strict: float | None
    semantic: float


def violation_cents(entry: str) -> int | None:
    """The cents a money-violation entry names, or None for another failure."""
    if not entry.startswith(MONEY_PREFIX):
        return None
    raw = entry[len(MONEY_PREFIX) :]
    try:
        figure = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return None
    if not isinstance(figure, str):
        return None
    figures = extract_monetary_figures(figure)
    return figures[0].cents if figures else None


def clean_money_violations(
    entries: Sequence[str],
    *,
    catalog_cents: set[int],
    answer_cents: set[int],
) -> tuple[list[str], list[str]]:
    """Split the money violations a catalog price explains from the rest.

    An entry is cleared only when its figure is both in the tenant catalog and
    actually present in this case's answer. A failure that is not a money
    violation is returned in ``kept`` untouched.
    """
    kept: list[str] = []
    cleared: list[str] = []
    for entry in entries:
        cents = violation_cents(entry)
        if cents is not None and cents in catalog_cents and cents in answer_cents:
            cleared.append(entry)
        else:
            kept.append(entry)
    return kept, cleared


def rescore_case_money(case: dict[str, Any], *, catalog_cents: set[int]) -> MoneyChange:
    """Clear catalog-sourced money violations and rebuild the case's failures.

    ``tool_correctness`` exists on trajectory cases and is ``not failures``, so
    clearing the only failure flips it back to 1.0. Generation cases carry no
    such score and are left with their other scores untouched.
    """
    answer = str(case.get("answer") or "")
    figures = extract_monetary_figures(answer)
    answer_cents = {figure.cents for figure in figures}
    entries = [str(entry) for entry in case.get("money_violations") or []]
    kept, cleared = clean_money_violations(
        entries, catalog_cents=catalog_cents, answer_cents=answer_cents
    )

    non_money = [
        str(failure)
        for failure in case.get("failures") or []
        if not str(failure).startswith(MONEY_PREFIX)
    ]
    case["money_violations"] = kept
    case["failures"] = non_money + kept

    scores = case.get("scores")
    if isinstance(scores, dict) and "tool_correctness" in scores:
        scores["tool_correctness"] = 0.0 if case["failures"] else 1.0

    return MoneyChange(
        case_id=str(case.get("case_id")),
        repeat=case.get("repeat"),
        before=len(entries),
        after=len(kept),
        cleared=cleared,
    )


def _tenant_slug(case_id: str) -> str:
    prefix = case_id.split("/", 1)[0] if "/" in case_id else "tenant1"
    return _TENANT_SLUGS.get(prefix, TENANT1_SLUG)


async def _prices_by_tenant(
    suites: dict[str, list[dict[str, Any]]],
) -> dict[str, set[int]]:
    """One catalog query per tenant that actually has a money case."""
    needed = {
        _tenant_slug(str(case.get("case_id")))
        for cases in suites.values()
        for case in cases
        if case.get("money_violations")
    }
    prices: dict[str, set[int]] = {}
    for slug in sorted(needed):
        tenant_id: UUID | None = await tenant_id_for(slug)
        if tenant_id is None:
            raise RescoreError(f"tenant {slug!r} is not seeded; run make seed-tenant1")
        prices[slug] = await offering_price_cents(tenant_id)
    return prices


def _aggregate_mean(aggregate: dict[str, Any], criterion: str) -> tuple[float | None, int | None]:
    stat = (aggregate.get("criteria") or {}).get(criterion) or {}
    return stat.get("mean"), stat.get("n")


def _changed_criteria(
    before: dict[str, Any], after: dict[str, Any], *, allowed: Sequence[str]
) -> list[str]:
    old = before.get("criteria") or {}
    new = after.get("criteria") or {}
    allowed_set = set(allowed)
    changed = []
    for name in sorted(set(old) | set(new)):
        if name in allowed_set:
            continue
        if (old.get(name) or {}).get("mean") != (new.get(name) or {}).get("mean"):
            changed.append(name)
    return changed


def _write_atomic(path: Path, artifact: dict[str, Any], secrets: Sequence[str]) -> None:
    payload = json.dumps(_redact_tree(artifact, secrets), indent=2) + "\n"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(payload)
    os.replace(temporary, path)


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{float(value):.3f}"


def _status(verdict: Any) -> str:
    return str((verdict or {}).get("status")) if isinstance(verdict, dict) else "n/a"


def _reasons(verdict: Any) -> str:
    if not isinstance(verdict, dict):
        return "n/a"
    reasons = verdict.get("reasons") or []
    return "; ".join(str(reason) for reason in reasons) or "-"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text())


async def rescore(artifact_path: Path, *, config_path: Path, dry_run: bool, out: Path) -> int:
    raw = _load_json(artifact_path)
    if not isinstance(raw, dict):
        raise RescoreError(f"{artifact_path}: top level is not an object")
    artifact: dict[str, Any] = raw

    suites = {
        name: artifact[name]["cases"]
        for name in _SUITES
        if isinstance(artifact.get(name), dict)
        and isinstance(artifact[name].get("cases"), list)
        and artifact[name]["cases"]
    }
    if not suites:
        print(f"{artifact_path}: no trajectory or generation cases; leaving it untouched")
        return 0

    config = load_config(config_path)
    judge = MeteredProvider(
        build_provider(config.judge, max_tokens_draft=0),
        role="judge",
        label=config.judge.label,
    )

    created_pool = False
    try:
        db.get_pool()
    except RuntimeError:
        await db.create_pool()
        created_pool = True

    try:
        prices = await _prices_by_tenant(suites)
        money_changes: list[MoneyChange] = []
        refusal_changes: list[RefusalChange] = []

        for name in _SUITES:
            for case in suites.get(name, []):
                if not isinstance(case, dict):
                    continue
                case_id = str(case.get("case_id"))
                catalog_cents = prices.get(_tenant_slug(case_id), set())
                if case.get("money_violations") or extract_monetary_figures(
                    str(case.get("answer") or "")
                ):
                    money_changes.append(rescore_case_money(case, catalog_cents=catalog_cents))

                if (
                    name == "generation"
                    and case.get("category") == "negative"
                    and str(case.get("answer") or "").strip()
                ):
                    question = str(case.get("question") or "")
                    answer = str(case.get("answer") or "")
                    print(f"[refusal] {case_id} repeat {case.get('repeat')}", flush=True)
                    semantic = await score_semantic_refusal(question, answer, judge=judge)
                    scores = case.get("scores")
                    if not isinstance(scores, dict):
                        scores = {}
                        case["scores"] = scores
                    scores["refusal_semantic"] = semantic
                    refusal_changes.append(
                        RefusalChange(
                            case_id=case_id,
                            repeat=case.get("repeat"),
                            strict=(scores.get("refusal_correct")),
                            semantic=semantic,
                        )
                    )
    finally:
        if created_pool:
            await db.close_pool()

    generation_before = json.loads(
        json.dumps((artifact.get("generation") or {}).get("aggregate") or {})
    )
    artifact_before = json.loads(json.dumps(artifact.get("aggregate") or {}))
    verdict_before = json.loads(json.dumps(artifact.get("verdict")))

    for name, cases in suites.items():
        artifact[name]["aggregate"] = aggregate_cases(cases, seed=BOOTSTRAP_SEED)

    options = options_from_command(artifact.get("command"))
    artifact = _finish_artifact(artifact, options, config)
    generation_after = (artifact.get("generation") or {}).get("aggregate") or {}

    print(f"\nartifact: {artifact_path}")
    print("cases by suite: " + ", ".join(f"{name}={len(cases)}" for name, cases in suites.items()))

    changed_money = [change for change in money_changes if change.before or change.after]
    print(f"\nmoney violations before/after per case ({len(changed_money)} case(s)):")
    if not changed_money:
        print("  none")
    for change in changed_money:
        print(f"  {change.case_id} repeat {change.repeat}: {change.before} -> {change.after}")
        for entry in change.cleared:
            print(f"    cleared: {entry}")

    strict_before, strict_n = _aggregate_mean(generation_before, "refusal_correct")
    strict_after, _ = _aggregate_mean(generation_after, "refusal_correct")
    semantic_before, _ = _aggregate_mean(generation_before, "refusal_semantic")
    semantic_after, semantic_n = _aggregate_mean(generation_after, "refusal_semantic")
    print("\nrefusal means over the negative cases:")
    print(f"  strict (n={strict_n}): {_fmt(strict_before)} -> {_fmt(strict_after)}")
    print(f"  semantic (n={semantic_n}): {_fmt(semantic_before)} -> {_fmt(semantic_after)}")
    for refusal_change in refusal_changes:
        print(
            f"  {refusal_change.case_id} repeat {refusal_change.repeat}: "
            f"strict={_fmt(refusal_change.strict)} semantic={_fmt(refusal_change.semantic)}"
        )

    tool_before, _ = _aggregate_mean(artifact_before, "tool_correctness")
    tool_after, _ = _aggregate_mean(artifact.get("aggregate") or {}, "tool_correctness")
    print(f"\ntool_correctness mean: {_fmt(tool_before)} -> {_fmt(tool_after)}")

    drifted = _changed_criteria(
        artifact_before,
        artifact.get("aggregate") or {},
        allowed=("tool_correctness", "refusal_semantic"),
    )
    print(
        "other criterion means unchanged: "
        + ("yes" if not drifted else "NO (" + ", ".join(drifted) + ")")
    )
    print(f"\nverdict: {_status(verdict_before)} -> {_status(artifact.get('verdict'))}")
    print(f"  before: {_reasons(verdict_before)}")
    print(f"  after:  {_reasons(artifact.get('verdict'))}")

    if dry_run:
        print("\ndry run: no files written")
        return 0

    secrets = _secrets([*config.candidates, config.judge, config.second_judge])
    backup = artifact_path.with_name(artifact_path.name + ".bak")
    if not backup.exists():
        shutil.copy2(artifact_path, backup)
    _write_atomic(out, artifact, secrets)
    print(f"\nbackup: {backup}")
    print(f"wrote {out}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--artifact", required=True, help="one raw benchmark JSON artifact")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="benchmark config path")
    parser.add_argument(
        "--dry-run", action="store_true", help="print before/after and write nothing"
    )
    parser.add_argument(
        "--out",
        default=None,
        help="output path (default: overwrite the artifact after writing a .bak)",
    )
    args = parser.parse_args()
    artifact_path = Path(args.artifact)
    out = Path(args.out) if args.out else artifact_path
    try:
        raise SystemExit(
            asyncio.run(
                rescore(
                    artifact_path,
                    config_path=Path(args.config),
                    dry_run=args.dry_run,
                    out=out,
                )
            )
        )
    except (RescoreError, ValueError, OSError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc
    except Exception as exc:  # a judge/provider failure must not print a traceback at the CLI
        print(f"ERROR: {type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
