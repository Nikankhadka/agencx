"""Slice-3 honesty check: how often do the eval's own questions take the new
branch on bytefix? Read-only replay of the generation cases through the graph
(no scoring, no judge calls, no eval_runs row)."""

import asyncio
import collections
import json
import logging

logging.basicConfig(level=logging.INFO)

from app.agents.graph import build_graph  # noqa: E402
from app.agents.state import AgentState, GraphContext  # noqa: E402
from app.llm.dependency import get_llm_provider  # noqa: E402
from app.llm.embedder import get_embedder  # noqa: E402
from app.retrieval.rerank import get_reranker  # noqa: E402
from app.shared import config, db  # noqa: E402
from evals.generation_eval import load_cases as load_generation_cases  # noqa: E402
from evals.injection_eval import load_cases as load_injection_cases  # noqa: E402
import sys  # noqa: E402

SLUG = sys.argv[1]
MODE = sys.argv[2]

SEEN: list[str] = []


class Capture(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        SEEN.append(record.getMessage())


logging.getLogger().addHandler(Capture())
for name in ("app.agents.agent_node", "app.agents.draft_node"):
    logging.getLogger(name).setLevel(logging.INFO)
    logging.getLogger(name).propagate = True


async def main() -> None:
    try:
        db.get_pool()
    except RuntimeError:
        await db.create_pool()
    async with db.tenant_context(None, "platform_admin") as conn:
        tenant_id = await conn.fetchval("select id from tenants where slug = $1", SLUG)
    settings = config.get_settings()
    provider = get_llm_provider()
    embedder = get_embedder(settings)
    reranker = get_reranker(settings)
    cases = load_generation_cases() if MODE == "generation" else load_injection_cases()
    print(f"tenant={SLUG} ({tenant_id}) cases={len(cases)}")

    totals = collections.Counter()
    rows = []
    for i, case in enumerate(cases, 1):
        async with db.tenant_context(tenant_id, "tenant_admin") as conn:
            conversation_id = await conn.fetchval(
                "insert into conversations (tenant_id) values ($1) returning id", tenant_id
            )
        state: AgentState = {
            "conversation_id": str(conversation_id),
            "tenant_id": str(tenant_id),
            "messages": ([{"role": "customer", "content": case.question}] if MODE == "generation" else list(case.messages)),
            "route": None,
            "route_confidence": None,
            "retrieved_chunks": [],
            "selections": [],
            "engine_quote": None,
            "draft_response": "",
            "inspection": None,
            "escalated": False,
        }
        before = len(SEEN)
        final = await build_graph().ainvoke(
            state,
            context=GraphContext(
                tenant_id=tenant_id, provider=provider, embedder=embedder, reranker=reranker
            ),
        )
        hits = collections.Counter(m for m in SEEN[before:])
        branch = (
            "grounded" if hits["agent grounded tool answer"] else
            "direct-P3" if hits["agent direct answer"] else
            "draft" if hits["agent draft"] else "?"
        )
        totals[branch] += 1
        totals[f"route:{final.get('route')}"] += 1
        rows.append((i, getattr(case, "question", MODE), branch, final.get("route"), final.get("author_node"),
                     hits["agent model call"], hits["agent tool"], hits["agent draft"],
                     len(final.get("retrieved_chunks") or [])))
        print(json.dumps({"i": i, "branch": branch, "route": final.get("route"),
                          "author": final.get("author_node"), "agent_rounds": hits["agent model call"],
                          "tools": hits["agent tool"], "draft": hits["agent draft"],
                          "chunks": len(final.get("retrieved_chunks") or []),
                          "answer_chars": len(final.get("draft_response") or "")}))
    print("TOTALS", json.dumps(dict(sorted(totals.items()))))


asyncio.run(main())
