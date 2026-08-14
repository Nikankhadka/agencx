"""T-007: knowledge document upload and listing.

Handlers only: request parsing and validation (doc_type whitelist, file
extension and size) plus response shaping. The upload pipeline lives in
controller.py / service.py. Stored filenames are always ``{document_id}{ext}``
so a crafted filename can never escape the tenant's upload directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.features.knowledge import controller
from app.llm.dependency import get_embedder_dependency
from app.llm.embedder import Embedder
from app.shared import auth

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

ALLOWED_EXTENSIONS = frozenset({".md", ".txt", ".pdf", ".csv", ".json"})
ALLOWED_DOC_TYPES = frozenset({"policy", "faq", "catalog", "price_list", "other", "website"})
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    doc_type: str
    status: str
    error: str | None


class UrlIngestRequest(BaseModel):
    url: str


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
) -> list[DocumentResponse]:
    rows = await controller.list_documents(tenant_id=admin.tenant_id)
    return [DocumentResponse(**row) for row in rows]


def _reject_upload(file: UploadFile, body: bytes, doc_type: str) -> str:
    """Validate the upload; returns the lowercased file extension. Raises
    422s for every rejection path so the admin surface shows the exact reason
    without touching the database."""
    if doc_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"doc_type must be one of {sorted(ALLOWED_DOC_TYPES)}",
        )
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"unsupported file type {ext!r} - allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )
    if len(body) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)}MB upload limit",
        )
    if not body:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="empty file")
    return ext


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
    embedder: Annotated[Embedder, Depends(get_embedder_dependency)],
    file: Annotated[UploadFile, File()],
    doc_type: Annotated[str, Form()],
) -> DocumentResponse:
    body = await file.read()
    ext = _reject_upload(file, body, doc_type)
    document_id = uuid4()
    row = await controller.upload_document(
        tenant_id=admin.tenant_id,
        document_id=document_id,
        # Display name: the admin's original filename, kept only as a column
        # value. service.py derives the disk path from {document_id}{ext}, so
        # the original filename is never used to build a filesystem path.
        filename=file.filename or "",
        doc_type=doc_type,
        body=body,
        embedder=embedder,
        extension=ext,
    )
    return DocumentResponse(**row)


@router.post("/{document_id}/reprocess", response_model=DocumentResponse)
async def reprocess_document(
    document_id: UUID,
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
    embedder: Annotated[Embedder, Depends(get_embedder_dependency)],
) -> DocumentResponse:
    row = await controller.reprocess_document(
        tenant_id=admin.tenant_id, document_id=document_id, embedder=embedder
    )
    return DocumentResponse(**row)


@router.post("/urls", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def ingest_url(
    admin: Annotated[auth.AuthedTenantAdmin, Depends(auth.require_tenant_admin)],
    embedder: Annotated[Embedder, Depends(get_embedder_dependency)],
    payload: UrlIngestRequest,
) -> DocumentResponse:
    url = payload.url.strip()
    if urlparse(url).scheme.lower() not in ("http", "https"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="url must be an absolute http:// or https:// URL",
        )
    document_id = uuid4()
    row = await controller.upload_url(
        tenant_id=admin.tenant_id, document_id=document_id, url=url, embedder=embedder
    )
    return DocumentResponse(**row)
