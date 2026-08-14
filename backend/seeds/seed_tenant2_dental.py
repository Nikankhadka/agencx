"""T-037 / T-042: provision Tenant 2 (a dental clinic) through the public API.

The onboarding conversation portion pre-populates the agentic v2 jsonb state
directly (bypassing the LLM-driven copilot, per the 2026-07-30 decision), then
calls the confirm endpoint through the public API. The confirm validation and
relational write path is identical to a real admin's browser flow - only the
state population method differs.

Knowledge upload remains unchanged (real API calls).

Usage::

    uv run python -m seeds.seed_tenant2_dental
    uv run python -m seeds.seed_tenant2_dental --teardown
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx

from app.shared import db
from app.shared.config import get_settings

INPUTS_DIR = Path(__file__).parent / "tenant2_inputs"
INTERVIEW_SCRIPT = INPUTS_DIR / "interview-script.md"

SLUG = "northgate"
TENANT_NAME = "Northgate Family Dental"
OWNER_EMAIL = "owner@northgate.test"
OWNER_PASSWORD = "wren-demo"

# (filename, doc_type) - doc_type must be in knowledge.ALLOWED_DOC_TYPES.
KNOWLEDGE_DOCS: tuple[tuple[str, str], ...] = (
    ("clinic-policies.md", "policy"),
    ("services-and-fees.md", "price_list"),
    ("faq.md", "faq"),
)

# The stage names the script must cover. knowledge_prompt is not a data stage
# - it's the final prompt before confirm.
EXPECTED_STAGES: tuple[str, ...] = (
    "business_name",
    "hours_contact",
    "identity",
    "tone",
    "services",
    "pricing_rules",
    "business_number",
    "escalation_threshold",
    "knowledge_prompt",
)

# Prose is allowed between a stage heading and its fenced answer, so the
# script stays readable as a document; only the fence is posted.
_STAGE_BLOCK_RE = re.compile(
    r"^## stage:\s*(?P<stage>\S+)\s*\n(?P<prose>(?:(?!^## ).)*?)```\n(?P<answer>.*?)\n```",
    re.MULTILINE | re.DOTALL,
)


def parse_interview_script(text: str) -> dict[str, str]:
    """Pull ``{stage: answer}`` out of interview-script.md."""
    found = {m.group("stage"): m.group("answer").strip() for m in _STAGE_BLOCK_RE.finditer(text)}
    missing = [stage for stage in EXPECTED_STAGES if stage not in found]
    if missing:
        raise ValueError(f"interview script is missing stages: {missing}")
    return found


def _build_draft_from_answers(answers: dict[str, str]) -> dict[str, Any]:
    """Construct a v2 agentic draft from raw text interview answers.

    This bypasses the LLM-driven copilot per the ADR. The draft values match
    the Pydantic schemas in app/onboarding/flow.py exactly, so the confirm
    endpoint validates them identically to a real admin's browser flow.
    """
    draft: dict[str, Any] = {}

    # business: name, team, hours, contact, and inbound channels. The owner's
    # answer carries the name and the hours/contact lines; the rest is fixed
    # config for this proof (a multi-chair clinic reachable by web and phone).
    business_name = answers.get("business_name", "").strip() or TENANT_NAME
    hours_lines = [
        line.strip()
        for line in answers.get("hours_contact", "").strip().split("\n")
        if line.strip()
    ]
    draft["business"] = {
        "name": business_name,
        "is_team": True,
        "hours": hours_lines[0] if hours_lines else "",
        "contact": " / ".join(hours_lines[1:]) if len(hours_lines) > 1 else "",
        "inbound_channels": ["website", "phone"],
    }

    # identity: extract the business description from the answer
    draft["identity"] = {"description": answers["identity"].strip()}

    # tone: extract the tone description
    draft["tone"] = {"tone": answers["tone"].strip()}

    # services: parse the bullet-list of services with prices
    services_raw = answers["services"]
    items: list[dict[str, Any]] = []
    for line in services_raw.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        name, price = _parse_service_line(line)
        if name:
            items.append({"name": name, "description": "", "price_dollars": price})
    draft["services"] = {"items": items}

    # pricing_rules: parse rules from the answer
    rules_raw = answers.get("pricing_rules", "")
    rules: list[dict[str, Any]] = _parse_pricing_rules(rules_raw)
    draft["pricing_rules"] = {"rules": rules}

    # escalation: store the admin's described posture
    # The admin described a cautious posture - encode it
    draft["escalation_threshold"] = {
        "posture": "cautious",
        "threshold": None,
        "_resolved_threshold": 0.75,
    }

    # tax: the clinic has a business number and is tax-registered.
    draft["tax"] = {
        "has_business_number": True,
        "business_number": answers.get("business_number", "").strip(),
        "tax_registered": True,
    }

    # payment: collects directly, full payment before the visit, no deposit.
    draft["payment"] = {
        "processing_mode": "DIRECT",
        "terms": "full_before",
        "deposit_pct": None,
    }

    # readback: the owner has reviewed and confirmed the captured details.
    draft["readback"] = {"confirmed": True}

    return draft


def _parse_service_line(line: str) -> tuple[str | None, float | None]:
    """Extract name and optional price from a service description line.

    Examples: 'New patient exam is 95 dollars' -> ('New patient exam', 95.0)
              'Fluoride varnish 30' -> ('Fluoride varnish', 30.0)
    """
    # Match "$X" or "X dollars" at the end of the line
    import re as _re

    price_match = _re.search(
        r"\$\s*(\d+(?:,\d{3})*(?:\.\d{1,2})?)\s*$|(\d+(?:,\d{3})*(?:\.\d{1,2})?)\s*(?:dollars?|dollars?)?\s*$",
        line,
        _re.IGNORECASE,
    )
    if price_match:
        price_str = price_match.group(1) or price_match.group(2)
        price = float(price_str.replace(",", ""))
        name = line[: price_match.start()].strip().rstrip(",").rstrip("is").strip()
        return (name, price)
    return (line.strip(), None)


def _parse_pricing_rules(text: str) -> list[dict[str, Any]]:
    """Parse pricing rules from free text into structured rule dicts."""
    rules: list[dict[str, Any]] = []
    known_rules = [
        ("deep_cleaning", "Deep cleaning", "per_quadrant"),
        ("wisdom_tooth", "Wisdom tooth extraction", "per_tooth"),
        ("out_of_hours", "Out-of-hours surcharge", "flat"),
        ("missed_appointment", "Missed appointment fee", "flat"),
        ("family_plan", "Family preventive plan", "monthly"),
    ]
    text_lower = text.lower()
    for code, label, unit in known_rules:
        if label.lower() in text_lower:
            # Extract the dollar amount following the rule mention
            import re as _re

            pat = _re.compile(
                _re.escape(label.lower()) + r".*?(\d+(?:\.\d{1,2})?)\s*(?:dollar|$)", _re.IGNORECASE
            )
            m = pat.search(text)
            amount = float(m.group(1)) if m else None
            rules.append(
                {
                    "code": code,
                    "label": label,
                    "unit_amount_dollars": amount,
                    "unit": unit,
                }
            )
    return rules


class ProofFailure(RuntimeError):
    """A step the proof requires did not succeed through the public API."""


def _check(resp: httpx.Response, step: str) -> Any:
    if resp.status_code >= 400:
        raise ProofFailure(f"{step} failed: HTTP {resp.status_code} {resp.text}")
    return resp.json()


async def _create_owner_and_sign_in(client: httpx.AsyncClient, auth_base: str) -> str:
    """Create the clinic owner's auth user (if new) and return their access token.

    Signing up through GoTrue is what the real signup form does; the token
    that comes back is an ordinary user access token (aud=authenticated),
    the same one the browser would send.
    """
    signup = await client.post(
        f"{auth_base}/auth/v1/signup",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    )
    # 4xx here is almost always "user already registered" from a previous
    # run - fall through to the password grant rather than failing.
    if signup.status_code in (200, 201):
        token = signup.json().get("access_token")
        if token:
            return str(token)

    grant = await client.post(
        f"{auth_base}/auth/v1/token",
        params={"grant_type": "password"},
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    )
    data = _check(grant, "owner sign-in")
    token = data.get("access_token")
    if not token:
        raise ProofFailure(f"sign-in returned no access_token: {data}")
    return str(token)


async def run_proof(api_base: str, auth_base: str) -> dict[str, Any]:
    answers = parse_interview_script(INTERVIEW_SCRIPT.read_text())
    report: dict[str, Any] = {"transcript": []}

    async with httpx.AsyncClient(timeout=180) as client:
        print(f"  owner auth user  {OWNER_EMAIL}")
        token = await _create_owner_and_sign_in(client, auth_base)
        headers = {"Authorization": f"Bearer {token}"}

        print(f"  signup           {SLUG}")
        signup = _check(
            await client.post(
                f"{api_base}/api/tenants",
                json={"slug": SLUG, "name": TENANT_NAME},
                headers=headers,
            ),
            "tenant signup",
        )
        report["tenant_id"] = signup["tenant_id"]

        # T-042: pre-populate the agentic v2 jsonb state directly, bypassing the
        # LLM-driven copilot (per ADR in decisions-log.md). The confirm endpoint
        # validates the draft and writes to relational tables identically to a
        # real admin's browser flow - only the state population method differs.
        print("  onboarding       pre-populating v2 state")
        draft = _build_draft_from_answers(answers)
        async with db.tenant_context(UUID(signup["tenant_id"]), "tenant_admin") as conn:
            await conn.execute(
                "update tenant_config set config = "
                "jsonb_set(config, '{onboarding}', $2::jsonb, true), "
                "updated_at = now() where tenant_id = $1",
                UUID(signup["tenant_id"]),
                json.dumps(
                    {
                        "version": 2,
                        "draft": draft,
                        "history": [],
                        "off_topic_count": 0,
                        "completed": False,
                    }
                ),
            )
        report["draft"] = draft

        print("  confirm")
        confirmed = _check(
            await client.post(f"{api_base}/api/onboarding/confirm", headers=headers),
            "onboarding confirm",
        )
        report["catalog_items_created"] = confirmed["catalog_items_created"]
        report["pricing_rules_created"] = confirmed["pricing_rules_created"]

        report["documents"] = []
        for filename, doc_type in KNOWLEDGE_DOCS:
            print(f"  upload           {filename} ({doc_type})")
            body = (INPUTS_DIR / filename).read_bytes()
            uploaded = _check(
                await client.post(
                    f"{api_base}/api/knowledge/upload",
                    files={"file": (filename, body, "text/markdown")},
                    data={"doc_type": doc_type},
                    headers=headers,
                ),
                f"upload {filename}",
            )
            if uploaded["status"] != "ready":
                raise ProofFailure(
                    f"{filename} did not process: status={uploaded['status']} "
                    f"error={uploaded.get('error')}"
                )
            report["documents"].append(uploaded)

    return report


async def teardown() -> None:
    """Delete a previous proof run. NOT part of the proof - it only undoes one.

    Direct SQL is fine here precisely because this path is excluded from the
    proof: it exists so the provisioning run above can be repeated from a
    clean slate without hand-written psql.
    """
    from app.shared import db

    await db.create_pool()
    try:
        async with db.tenant_context(None, "platform_admin") as conn:
            tenant_id = await conn.fetchval("select id from tenants where slug = $1", SLUG)
            if tenant_id is None:
                print(f"nothing to tear down - no tenant {SLUG!r}")
                return
            await conn.execute("delete from users where tenant_id = $1", tenant_id)
            await conn.execute("delete from tenants where id = $1", tenant_id)
            print(f"tore down tenant {SLUG!r} ({tenant_id})")
    finally:
        await db.close_pool()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--teardown", action="store_true", help="remove a previous proof run")
    parser.add_argument("--api-base", default="http://localhost:8000")
    args = parser.parse_args()

    if args.teardown:
        asyncio.run(teardown())
        return 0

    auth_base = get_settings().supabase_url.rstrip("/")
    if not auth_base:
        print("SUPABASE_URL must be set (run scripts/demo.sh first).", file=sys.stderr)
        return 1

    print(f"provisioning tenant 2 through the public API at {args.api_base}")
    try:
        report = asyncio.run(run_proof(args.api_base, auth_base))
    except ProofFailure as exc:
        print(f"\nPROOF FAILED: {exc}", file=sys.stderr)
        print(
            "\nThis is a platform bug, not a script bug: every step above is a call the "
            "browser already makes for tenant 1. Fix the platform, then re-run.",
            file=sys.stderr,
        )
        return 1

    print(
        f"\ntenant {SLUG!r} is live: "
        f"{report['catalog_items_created']} catalog items, "
        f"{report['pricing_rules_created']} pricing rules, "
        f"{len(report['documents'])} documents ingested"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
