"""Knowledge feature orchestration for the API surface.

Pass-through layer between api.py (HTTP boundary, upload validation) and
service.py (persistence + ingestion pipeline). Keeps the document row
handling in one place so upload and reprocess share the same 404/500 logic.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.features.knowledge import service
from app.llm.embedder import Embedder


async def list_documents(*, tenant_id: UUID) -> list[dict[str, Any]]:
    return await service.list_documents(tenant_id=tenant_id)


async def upload_document(
    *,
    tenant_id: UUID,
    document_id: UUID,
    filename: str,
    doc_type: str,
    body: bytes,
    embedder: Embedder,
    extension: str,
) -> dict[str, Any]:
    row = await service.upload_document(
        tenant_id=tenant_id,
        document_id=document_id,
        filename=filename,
        doc_type=doc_type,
        body=body,
        embedder=embedder,
        extension=extension,
    )
    if row is None:
        # Cannot happen: process_document only updates the row it was given;
        # it never deletes it.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="document not created"
        )
    return row


async def reprocess_document(
    *, tenant_id: UUID, document_id: UUID, embedder: Embedder
) -> dict[str, Any]:
    row = await service.reprocess_document(
        tenant_id=tenant_id, document_id=document_id, embedder=embedder
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")
    return row


async def upload_url(
    *,
    tenant_id: UUID,
    document_id: UUID,
    url: str,
    embedder: Embedder,
) -> dict[str, Any]:
    """URL ingestion pass-through. ValueError (bad scheme, oversize, no content)
    becomes a 422; a missing resulting row a 500."""
    try:
        row = await service.upload_url(
            tenant_id=tenant_id, document_id=document_id, url=url, embedder=embedder
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="document not created"
        )
    return row
