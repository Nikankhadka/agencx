"""Offline re-score of citation faithfulness for one benchmark artifact.

The benchmark's citation score was graded against a 400-character slice of
each cited chunk, which cut the supporting sentence off in real bytefix chunks
(824 to 1859 chars). ``score_citation_faithfulness`` now receives the whole
chunk, but a finished artifact still carries the old, wrong scores. Re-running
the whole benchmark to fix them would spend hours of candidate calls, so this
tool re-asks the judge only the citation question for the cases that have one.

It reconstructs the exact chunk list the graph used - the bytefix tenant's
whole corpus, in ``whole_corpus`` order - and refuses to write anything if a
known citation no longer lands on the chunk it landed on when the diagnostic
ran (chunk 2 was ``policy.md`` for ``gen-001``). A re-score against the wrong
chunk order would be worse than no re-score.

Aggregation and the verdict are the benchmark's own functions
(``aggregate_cases`` / ``verdict``), so the artifact is judged exactly as a
fresh run judges it. Every other field, including the measured scores of every
other criterion, is preserved.

Usage::

    python -m evals.rescore_citations --artifact /evidence/raw/mistral.json --dry-run
    python -m evals.rescore_citations --artifact /evidence/raw/mistral.json
    python -m evals.rescore_citations --artifact /tmp/copy.json --out /tmp/fixed.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.agents.draft_node import citation_source
from app.services.context_package import build_package
from app.shared import db
from evals import generation_eval
from evals.model_benchmark import (
    BOOTSTRAP_SEED,
    DEFAULT_CONFIG,
    BenchmarkConfig,
    MeteredProvider,
    RunOptions,
    _artifact_suites,
    _combined_aggregate,
    _empty_required_suites,
    _redact_tree,
    _required_suites,
    _secrets,
    aggregate_cases,
    build_provider,
    load_config,
    tenant_id_for,
    verdict,
)
from seeds.seed_tenant1_phoneshop import SLUG as TENANT1_SLUG

_CITATION_RE = re.compile(r"\[\d+\]")
# The diagnostic that located this bug confirmed the reconstructed order by
# checking gen-001's citation: [2] was policy.md. Both complete artifacts from
# the 2026-10 run carry that citation, so a mismatch means the corpus order
# changed and no score here would be comparable to the run's other criteria.
ORDER_ANCHOR_CASE_ID = "gen-001"
ORDER_ANCHOR_INDEX = 2
ORDER_ANCHOR_SOURCE = "policy.md"


class RescoreError(RuntimeError):
    """The artifact or the reconstructed corpus cannot be re-scored safely."""


@dataclass(frozen=True)
class CaseChange:
    case_id: str
    repeat: int | None
    before: float | None
    after: float


def select_citation_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Positive cases whose answer is non-empty and carries a ``[n]`` marker."""
    selected = []
    for case in cases:
        answer = str(case.get("answer") or "").strip()
        if case.get("category") != "positive" or not answer:
            continue
        if _CITATION_RE.search(answer):
            selected.append(case)
    return selected


def verify_chunk_order(sources: list[str], cases: list[dict[str, Any]]) -> None:
    """Refuse to score when the rebuilt corpus does not match the run's order."""
    if len(sources) < ORDER_ANCHOR_INDEX:
        raise RescoreError(
            f"rebuilt corpus has {len(sources)} chunk(s); cannot confirm chunk "
            f"{ORDER_ANCHOR_INDEX} is {ORDER_ANCHOR_SOURCE}"
        )
    found = sources[ORDER_ANCHOR_INDEX - 1]
    if found != ORDER_ANCHOR_SOURCE:
        raise RescoreError(
            f"chunk {ORDER_ANCHOR_INDEX} is {found!r}, expected {ORDER_ANCHOR_SOURCE!r}; "
            "the rebuilt corpus order does not match the benchmark artifact"
        )
    anchor = next((case for case in cases if case.get("case_id") == ORDER_ANCHOR_CASE_ID), None)
    if anchor is None:
        raise RescoreError(
            f"artifact has no {ORDER_ANCHOR_CASE_ID}; cannot confirm the order against a citation"
        )
    cited = [int(match[1:-1]) for match in _CITATION_RE.findall(str(anchor.get("answer") or ""))]
    if ORDER_ANCHOR_INDEX not in cited:
        raise RescoreError(
            f"{ORDER_ANCHOR_CASE_ID} does not cite [{ORDER_ANCHOR_INDEX}]; cannot confirm "
            "the rebuilt corpus order against the artifact"
        )


def apply_rescore(
    artifact: dict[str, Any],
    *,
    config: BenchmarkConfig,
    changes: list[CaseChange],
) -> dict[str, Any]:
    """Update citation scores in place and rebuild both aggregates and verdict.

    Every other artifact field is left untouched. The verdict is rebuilt with
    the benchmark's own helpers and thresholds, including the capability gate
    override a fresh run applies.
    """
    generation = artifact.get("generation")
    if not isinstance(generation, dict) or not isinstance(generation.get("cases"), list):
        raise RescoreError("artifact has no generation.cases")
    by_key = {(str(case.get("case_id")), case.get("repeat")): case for case in generation["cases"]}
    for change in changes:
        case = by_key.get((change.case_id, change.repeat))
        if case is None:
            raise RescoreError(f"case {change.case_id} repeat {change.repeat} disappeared")
        scores = case.get("scores")
        if not isinstance(scores, dict):
            scores = {}
            case["scores"] = scores
        scores["citation_faithfulness"] = change.after

    generation["aggregate"] = aggregate_cases(generation["cases"], seed=BOOTSTRAP_SEED)
    artifact["aggregate"] = _combined_aggregate(artifact)

    options = options_from_command(artifact.get("command"))
    artifact["verdict"] = verdict(
        artifact["aggregate"],
        config.thresholds,
        suites_present=_artifact_suites(artifact),
        suites_required=_required_suites(options),
        suites_empty=_empty_required_suites(artifact, options),
    )
    gate = artifact.get("gate") or {}
    if gate.get("status") in ("completed", "failed") and not gate.get("qualified"):
        artifact["verdict"] = {
            "status": "FAIL",
            "reasons": [
                f"capability gate: {gate.get('error') or 'not qualified'}",
                *artifact["verdict"]["reasons"],
            ],
        }
    return artifact


def options_from_command(command: Any) -> RunOptions:
    """The run shape an artifact records, enough to rebuild its verdict."""
    suite = "all"
    if isinstance(command, str):
        try:
            parts = shlex.split(command)
        except ValueError:
            parts = []
        if "--suite" in parts:
            index = parts.index("--suite")
            if index + 1 < len(parts):
                suite = parts[index + 1]
    return RunOptions(
        models=None,
        suite=suite,
        repeats=None,
        limit=None,
        resume=False,
        refresh_gate=False,
        report_only=False,
        out=Path("."),
        config_path=Path("."),
    )


def _aggregate_mean(aggregate: dict[str, Any], criterion: str) -> tuple[float | None, int | None]:
    stat = (aggregate.get("criteria") or {}).get(criterion) or {}
    return stat.get("mean"), stat.get("n")


def _criteria_unchanged(before: dict[str, Any], after: dict[str, Any], *, ignore: str) -> list[str]:
    """Criteria whose means moved unexpectedly, excluding the re-scored one."""
    old = before.get("criteria") or {}
    new = after.get("criteria") or {}
    changed = []
    for name in sorted(set(old) | set(new)):
        if name == ignore:
            continue
        if (old.get(name) or {}).get("mean") != (new.get(name) or {}).get("mean"):
            changed.append(name)
    return changed


def _write_atomic(path: Path, artifact: dict[str, Any], secrets: list[str]) -> None:
    payload = json.dumps(_redact_tree(artifact, secrets), indent=2) + "\n"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(payload)
    os.replace(temporary, path)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text())


async def rescore(artifact_path: Path, *, config_path: Path, dry_run: bool, out: Path) -> int:
    artifact = _load_json(artifact_path)
    if not isinstance(artifact, dict):
        raise RescoreError(f"{artifact_path}: top level is not an object")
    generation = artifact.get("generation")
    if not isinstance(generation, dict) or not isinstance(generation.get("cases"), list):
        raise RescoreError(f"{artifact_path}: no generation.cases to re-score")
    cases: list[dict[str, Any]] = generation["cases"]
    selected = select_citation_cases(cases)
    if not selected:
        raise RescoreError("no positive, cited cases to re-score")

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
        tenant_id = await tenant_id_for(TENANT1_SLUG)
        if tenant_id is None:
            raise RescoreError(
                f"tenant {TENANT1_SLUG!r} is not seeded; run make seed-tenant1 before re-scoring"
            )
        async with db.tenant_context(tenant_id, "tenant_admin") as conn:
            package = await build_package(conn, tenant_id)
        if not package.chunks:
            raise RescoreError(
                "the context package has no chunks (the tenant is on the hybrid path); "
                "the graph's chunk order cannot be reconstructed"
            )
        verify_chunk_order(
            [citation_source({"metadata": chunk.metadata}) for chunk in package.chunks], cases
        )
        chunks = [{"content": chunk.content} for chunk in package.chunks]

        changes: list[CaseChange] = []
        for position, case in enumerate(selected, start=1):
            case_id = str(case.get("case_id"))
            repeat = case.get("repeat")
            before = (case.get("scores") or {}).get("citation_faithfulness")
            print(f"[{position}/{len(selected)}] {case_id} repeat {repeat}", flush=True)
            citation_verdicts = await generation_eval.score_citation_faithfulness(
                str(case.get("answer") or ""), chunks, provider=judge
            )
            after = generation_eval.citation_faithfulness_score(
                [item.supported for item in citation_verdicts]
            )
            changes.append(
                CaseChange(
                    case_id=case_id,
                    repeat=repeat,
                    before=before,
                    after=after,
                )
            )
    finally:
        if created_pool:
            await db.close_pool()

    generation_before = json.loads(json.dumps(generation.get("aggregate") or {}))
    artifact_before = json.loads(json.dumps(artifact.get("aggregate") or {}))
    verdict_before = json.loads(json.dumps(artifact.get("verdict")))

    apply_rescore(artifact, config=config, changes=changes)

    citation_before, citation_n = _aggregate_mean(generation_before, "citation_faithfulness")
    citation_after, _ = _aggregate_mean(generation["aggregate"], "citation_faithfulness")
    wide_before, _ = _aggregate_mean(artifact_before, "citation_faithfulness")
    wide_after, _ = _aggregate_mean(artifact["aggregate"], "citation_faithfulness")

    print(f"\nartifact: {artifact_path}")
    print(f"cases in artifact: {len(cases)}")
    print(f"positive cases with citations: {len(selected)}")
    print(f"cases re-scored: {len(changes)}")
    print(
        f"citation mean (generation, n={citation_n}): "
        f"{_fmt(citation_before)} -> {_fmt(citation_after)}"
    )
    print(f"citation mean (artifact-wide): {_fmt(wide_before)} -> {_fmt(wide_after)}")
    changed = [change for change in changes if not _same(change.before, change.after)]
    print(f"cases whose score changed: {len(changed)}")
    for change in changed:
        print(
            f"  {change.case_id} repeat {change.repeat}: "
            f"{_fmt(change.before)} -> {_fmt(change.after)}"
        )
    drifted = _criteria_unchanged(
        generation_before, generation["aggregate"], ignore="citation_faithfulness"
    )
    print(
        "other generation criterion means unchanged: "
        + ("yes" if not drifted else "NO (" + ", ".join(drifted) + ")")
    )
    wide_drift = _criteria_unchanged(
        artifact_before, artifact["aggregate"], ignore="citation_faithfulness"
    )
    print(
        "other artifact-wide criterion means unchanged: "
        + ("yes" if not wide_drift else "NO (" + ", ".join(wide_drift) + ")")
    )
    print(
        "verdict: "
        f"{verdict_before.get('status') if isinstance(verdict_before, dict) else 'n/a'} -> "
        f"{artifact['verdict']['status']}"
    )
    print(f"judge calls: {len(judge.records)}")
    failed_calls = sum(1 for record in judge.records if not record.ok)
    print(f"judge call failures: {failed_calls}")

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


def _same(before: float | None, after: float) -> bool:
    return before is not None and abs(float(before) - float(after)) < 1e-12


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{float(value):.3f}"


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--artifact", required=True, help="one raw benchmark JSON artifact")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="benchmark config path")
    parser.add_argument(
        "--dry-run", action="store_true", help="print before/after means and write nothing"
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
