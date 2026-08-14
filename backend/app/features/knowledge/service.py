"""Knowledge persistence: document-row queries + the upload pipeline.

Moved from api/knowledge.py. Raw files land on local disk under
``{uploads_dir}/{tenant_id}/`` (path from settings); only the ``documents`` row
is queried by the rest of the app. Stored filenames are always
``{document_id}{ext}`` - the admin's original filename is kept only as a column
value, never used to build a filesystem path, so a crafted filename
(``../../etc/passwd``) can't escape the tenant's upload directory. Chunking and
embedding run through app.ingestion.pipeline.process_document, which needs an
open ``tenant_context`` connection - it is called inside the context here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from starlette.concurrency import run_in_threadpool

from app.ingestion.pipeline import process_document
from app.ingestion.url import extract_main_text, extract_title, fetch_page
from app.llm.embedder import Embedder
from app.shared import db
from app.shared.config import get_settings

_SELECT_COLUMNS = "id, filename, doc_type, status, error"


def _write_upload(path: Path, body: bytes) -> None:
    """Blocking filesystem write - always run via ``run_in_threadpool``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


async def list_documents(*, tenant_id: UUID) -> list[dict[str, Any]]:
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        rows = await conn.fetch(
            f"select {_SELECT_COLUMNS} from documents "
            "where tenant_id = $1 order by uploaded_at desc",
            tenant_id,
        )
    return [dict(row) for row in rows]


async def upload_document(
    *,
    tenant_id: UUID,
    document_id: UUID,
    filename: str,
    doc_type: str,
    body: bytes,
    embedder: Embedder,
    extension: str,
) -> dict[str, Any] | None:
    """Write the upload to disk (never trusting the client filename for the
    path - the disk name is always ``{document_id}{extension}``), insert the
    pending documents row keeping the admin's original filename as the display
    column, then run the ingestion pipeline to completion. Returns the
    resulting row."""
    document_path = Path(get_settings().uploads_dir) / str(tenant_id) / f"{document_id}{extension}"
    await run_in_threadpool(_write_upload, document_path, body)

    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        await conn.execute(
            "insert into documents (id, tenant_id, filename, doc_type, status) "
            "values ($1, $2, $3, $4, 'pending')",
            document_id,
            tenant_id,
            filename,
            doc_type,
        )
        await process_document(
            conn, tenant_id=tenant_id, document_id=document_id, embedder=embedder
        )
        row = await conn.fetchrow(
            f"select {_SELECT_COLUMNS} from documents where id = $1", document_id
        )
    return dict(row) if row is not None else None


async def upload_url(
    *,
    tenant_id: UUID,
    document_id: UUID,
    url: str,
    embedder: Embedder,
) -> dict[str, Any] | None:
    """Fetch a URL, extract its main text, and ingest it as a 'website' document.

    The extracted text is written to disk as ``{document_id}.txt`` (never a
    client-controlled path - same posture as ``upload_document``); the documents
    row stores the URL as its display filename only. Idempotent: re-pasting a
    URL this tenant already ingested returns the existing row untouched.
    Raises ``ValueError`` when the page has no extractable text.
    """
    html = await fetch_page(url)
    text = extract_main_text(html)
    if not text:
        raise ValueError("no extractable content at this URL")
    title = extract_title(html) or url

    document_path = Path(get_settings().uploads_dir) / str(tenant_id) / f"{document_id}.txt"
    await run_in_threadpool(_write_upload, document_path, text.encode("utf-8"))

    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        existing = await conn.fetchrow(
            f"select {_SELECT_COLUMNS} from documents "
            "where tenant_id = $1 and doc_type = 'website' and filename = $2",
            tenant_id,
            url,
        )
        if existing is not None:
            return dict(existing)
        await conn.execute(
            "insert into documents (id, tenant_id, filename, doc_type, status) "
            "values ($1, $2, $3, 'website', 'pending')",
            document_id,
            tenant_id,
            url,
        )
        await process_document(
            conn,
            tenant_id=tenant_id,
            document_id=document_id,
            embedder=embedder,
            extension=".txt",
            source=title,
        )
        row = await conn.fetchrow(
            f"select {_SELECT_COLUMNS} from documents where id = $1", document_id
        )
    return dict(row) if row is not None else None


async def reprocess_document(
    *, tenant_id: UUID, document_id: UUID, embedder: Embedder
) -> dict[str, Any] | None:
    """Re-run the ingest pipeline for one document; None when the document is
    not this tenant's."""
    async with db.tenant_context(tenant_id, "tenant_admin") as conn:
        exists = await conn.fetchval(
            "select 1 from documents where id = $1 and tenant_id = $2",
            document_id,
            tenant_id,
        )
        if not exists:
            return None
        await process_document(
            conn, tenant_id=tenant_id, document_id=document_id, embedder=embedder
        )
        row = await conn.fetchrow(
            f"select {_SELECT_COLUMNS} from documents where id = $1", document_id
        )
    return dict(row) if row is not None else None
