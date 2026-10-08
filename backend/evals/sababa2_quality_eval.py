"""Faithfulness, answer relevancy and trajectory scores for the sababa2 demo tenant.

Reuses generation_eval's judges (faithfulness = claims supported by the tenant's
own material, relevancy = embedding similarity of questions the answer implies)
and trajectory_eval's scorer (route, selections, terminal state, step
efficiency). Faithfulness and relevancy score a frozen sample of replies that
were actually served (datasets/sababa2_quality_sample.jsonl); trajectory drives
the real graph on datasets/sababa2_trajectory.jsonl.

    python -m evals.sababa2_quality_eval --part rag|trajectory [--out FILE]
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from app.llm.dependency import get_llm_provider
from app.llm.embedder import get_embedder
from app.retrieval.rerank import get_reranker
from app.services.context_package import build_package
from app.shared import config, db
from evals import generation_eval, trajectory_eval
from evals.trajectory_dataset import load_cases

SLUG = "sababa2"
DATASETS = Path(__file__).parent / "datasets"
PACE_S = 20  # seconds between judged replies: each sends the whole corpus several times


async def _rag(tenant_id: UUID, out: dict[str, Any], prior: list[dict[str, Any]]) -> None:
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        package = await build_package(conn, tenant_id)
    context = "\n\n".join([package.owner_material(), *(c.content for c in package.chunks)])
    provider, embedder = get_llm_provider(), get_embedder(config.get_settings())
    rows = [
        json.loads(line)
        for line in (DATASETS / "sababa2_quality_sample.jsonl").read_text().splitlines()
        if line.strip() and "case_id" in line
    ]
    done = {r["case_id"]: r for r in prior if "error" not in r}  # resume: keep scored replies
    results = []
    streak = 0  # consecutive failures: stop instead of burning quota on a dead provider
    for i, row in enumerate(rows, start=1):
        if row["case_id"] in done:
            results.append(done[row["case_id"]])
            continue
        rec = {"case_id": row["case_id"], "group": row["group"], "question": row["question"]}
        try:
            verdicts = await generation_eval.score_faithfulness(
                row["reply"], context, provider=provider
            )
            supported = [v.supported for v in verdicts]
            rec["faithfulness"] = generation_eval.faithfulness_score(supported)
            rec["unsupported"] = [v.claim for v in verdicts if not v.supported]
            rec["claims"] = len(verdicts)
            rec["relevancy"] = await generation_eval.answer_relevancy(
                row["question"], row["reply"], provider=provider, embedder=embedder
            )
        except Exception as exc:  # recorded as a finding, not retried
            rec["error"] = repr(exc)[:300]
        shown = (
            rec["case_id"],
            rec.get("faithfulness"),
            rec.get("relevancy"),
            rec.get("error", ""),
        )
        print(f"[{i}/{len(rows)}]", *shown, flush=True)
        results.append(rec)
        streak = streak + 1 if "error" in rec else 0
        if streak >= 3:
            print("STOP: 3 consecutive failures, remaining replies not scored", flush=True)
            break
        await asyncio.sleep(PACE_S)
    out["rag"] = results


async def _trajectory(tenant_id: UUID, out: dict[str, Any]) -> None:
    metrics, scores = await trajectory_eval.run_eval(
        tenant_id=tenant_id,
        cases=load_cases(DATASETS / "sababa2_trajectory.jsonl"),
        provider=get_llm_provider(),
        embedder=get_embedder(config.get_settings()),
        reranker=get_reranker(config.get_settings()),
    )
    cases = []
    for s in scores:
        if s.trajectory is None:
            continue
        final = s.trajectory.final_state
        cases.append(
            {
                "case_id": s.case_id,
                "category": s.category,
                "correct": s.correct,
                "failures": s.failures,
                "steps": [st.node for st in s.trajectory.steps],
                "steps_expected_min": s.steps_expected_min,
                "efficiency": s.efficiency,
                "reasoning_grade": s.reasoning_grade,
                "route": final.get("route"),
                "draft": final.get("draft_response", ""),
            }
        )
    out["trajectory"] = {"metrics": metrics, "cases": cases}


async def main_async(part: str, out_path: str, resume: bool) -> None:
    await db.create_pool()
    try:
        async with db.tenant_context(None, "platform_admin") as conn:
            tenant_id = await conn.fetchval("select id from tenants where slug = $1", SLUG)
        out: dict[str, Any] = {}
        if part == "rag":
            prior = (
                json.loads(await asyncio.to_thread(Path(out_path).read_text))["rag"]
                if resume
                else []
            )
            await _rag(tenant_id, out, prior)
        else:
            await _trajectory(tenant_id, out)
        body = json.dumps(out, indent=1, default=str)
        await asyncio.to_thread(Path(out_path).write_text, body)
    finally:
        await db.close_pool()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["rag", "trajectory"], required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--resume", action="store_true", help="keep replies already scored in --out")
    args = ap.parse_args()
    asyncio.run(main_async(args.part, args.out, args.resume))
