"""Slice 4: how much wall clock can the sparse/embed overlap actually save?

Times the stages the change reorders, separately, for the hybrid tenant's own
fixed messages: the overlap can save at most the sparse query's own duration
(plus whatever part of it the embedding covers).
"""

import asyncio
import logging
import statistics as st
import time

logging.basicConfig(level=logging.WARNING)

from app.llm.embedder import get_embedder  # noqa: E402
from app.retrieval.dense import dense_search  # noqa: E402
from app.retrieval.rerank import get_reranker  # noqa: E402
from app.retrieval.service import retrieve  # noqa: E402
from app.retrieval.sparse import sparse_search  # noqa: E402
from app.shared import config, db  # noqa: E402

SLUG = "sababa"
QUERIES = [
    "Which dishes are vegan or gluten free?",
    "What are your most popular items?",
    "What time do you open?",
    "Do you have anything without nuts?",
    "What is the Super Plate?",
]


async def main() -> None:
    try:
        db.get_pool()
    except RuntimeError:
        await db.create_pool()
    settings = config.get_settings()
    embedder = get_embedder(settings)
    reranker = get_reranker(settings)
    async with db.tenant_context(None, "platform_admin") as conn:
        tenant_id = await conn.fetchval("select id from tenants where slug = $1", SLUG)
    print(f"tenant={SLUG} ({tenant_id}) queries={len(QUERIES)}")

    rows = []
    async with db.tenant_context(tenant_id, "customer") as conn:
        for query in QUERIES:
            t0 = time.perf_counter()
            vector = (await embedder.embed([query]))[0]
            embed = (time.perf_counter() - t0) * 1000
            t0 = time.perf_counter()
            await dense_search(conn, tenant_id=tenant_id, query_embedding=vector)
            dense = (time.perf_counter() - t0) * 1000
            t0 = time.perf_counter()
            await sparse_search(conn, tenant_id=tenant_id, query=query)
            sparse = (time.perf_counter() - t0) * 1000
            t0 = time.perf_counter()
            await retrieve(conn, tenant_id=tenant_id, query=query, embedder=embedder, reranker=reranker)
            whole = (time.perf_counter() - t0) * 1000
            rows.append((query, embed, dense, sparse, whole))
            print(
                f"  {query[:40]:42s} embed={embed:7.1f} dense={dense:6.2f} sparse={sparse:6.2f} retrieve={whole:7.1f}"
            )

    def med(i: int) -> float:
        return round(st.median([r[i] for r in rows]), 2)

    print(f"MEDIAN embed={med(1)} dense={med(2)} sparse={med(3)} retrieve_total={med(4)}")
    print(f"MAX saving available from the overlap (sparse alone) = {round(max(r[3] for r in rows), 2)} ms")


asyncio.run(main())
