"""Raw upload storage: one interface, two implementations.

Uploaded files have to outlive the request that wrote them. ``draft_from_upload``
parks a draft without chunking anything, and the chunk+embed pass in
app/ingestion/pipeline.py reads the file back during a *later* request when the
owner saves it. On a host whose container filesystem is per-instance and
ephemeral (Vercel container services) that read lands on a different machine,
raises ``FileNotFoundError``, and the document is silently marked ``failed``.

``get_storage`` picks the implementation from ``settings.uploads_bucket`` -
never a literal at the call site, matching the reranker and LLM provider
abstractions (app/retrieval/rerank.py, app/llm/provider.py). Empty bucket means
local disk, which keeps ``make dev`` and the test suite on the filesystem.

Keys are always ``{tenant_id}/{document_id}{ext}``: the admin's original
filename is a column value, never part of a path, so a crafted name
(``../../etc/passwd``) cannot escape the tenant's prefix.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from uuid import UUID

import httpx
from starlette.concurrency import run_in_threadpool

from app.shared.config import get_settings


class Storage(ABC):
    @abstractmethod
    async def put(self, key: str, body: bytes) -> None:
        """Write ``body`` at ``key``, replacing anything already there."""

    @abstractmethod
    async def get(self, key: str) -> bytes | None:
        """Read ``key``, or ``None`` when it does not exist.

        Missing is a normal outcome, not an error: a catalog document is
        synthesized from rows and has no file at all.
        """

    @abstractmethod
    async def delete_prefix(self, prefix: str) -> None:
        """Delete every object whose key starts with ``prefix``.

        Used to forget one document's files without knowing which extension it
        landed under. A no-op when nothing matches.
        """


def _write_file(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


def _read_file(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def _delete_matching(root: Path, prefix: str) -> None:
    directory = root / prefix
    parent, stem = (directory.parent, directory.name)
    if not parent.exists():
        return
    for path in parent.glob(f"{stem}*"):
        path.unlink()


class LocalStorage(Storage):
    """Filesystem under ``settings.uploads_dir`` - the dev and test path."""

    def __init__(self, root: str) -> None:
        self._root = Path(root)

    async def put(self, key: str, body: bytes) -> None:
        await run_in_threadpool(_write_file, self._root / key, body)

    async def get(self, key: str) -> bytes | None:
        return await run_in_threadpool(_read_file, self._root / key)

    async def delete_prefix(self, prefix: str) -> None:
        await run_in_threadpool(_delete_matching, self._root, prefix)


class SupabaseStorage(Storage):
    """Supabase Storage over its REST API - no SDK dependency for three calls,
    the same posture as the Cohere reranker (app/retrieval/rerank.py)."""

    def __init__(self, *, base_url: str, bucket: str, service_role_key: str) -> None:
        self._bucket = bucket
        self._client = httpx.AsyncClient(
            base_url=f"{base_url.rstrip('/')}/storage/v1",
            headers={
                "Authorization": f"Bearer {service_role_key}",
                "apikey": service_role_key,
            },
            timeout=30,
        )

    async def put(self, key: str, body: bytes) -> None:
        resp = await self._client.post(
            f"/object/{self._bucket}/{key}",
            content=body,
            headers={"Content-Type": "application/octet-stream", "x-upsert": "true"},
        )
        resp.raise_for_status()

    async def get(self, key: str) -> bytes | None:
        resp = await self._client.get(f"/object/{self._bucket}/{key}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.content

    async def delete_prefix(self, prefix: str) -> None:
        # Storage has no delete-by-prefix, so list the tenant folder and filter.
        # `prefix` is always "{tenant_id}/{document_id}", one document's files.
        folder, _, stem = prefix.rpartition("/")
        listing = await self._client.post(
            f"/object/list/{self._bucket}",
            json={"prefix": folder, "limit": 100},
        )
        listing.raise_for_status()
        names = [
            item["name"] for item in listing.json() if str(item.get("name", "")).startswith(stem)
        ]
        if not names:
            return
        resp = await self._client.request(
            "DELETE",
            f"/object/{self._bucket}",
            json={"prefixes": [f"{folder}/{name}" for name in names]},
        )
        resp.raise_for_status()


@lru_cache(maxsize=4)
def _build(bucket: str, uploads_dir: str, base_url: str, service_role_key: str) -> Storage:
    if not bucket:
        return LocalStorage(uploads_dir)
    return SupabaseStorage(base_url=base_url, bucket=bucket, service_role_key=service_role_key)


def get_storage() -> Storage:
    """The storage backend for the current settings.

    Cached on the config values it depends on rather than outright, so the
    Supabase client reuses one connection pool while a test that repoints
    ``UPLOADS_DIR`` (and clears the settings cache) still gets fresh storage -
    a plain ``lru_cache`` here would hand back the previous temp directory.
    """
    settings = get_settings()
    return _build(
        settings.uploads_bucket,
        settings.uploads_dir,
        settings.supabase_url,
        settings.supabase_service_role_key,
    )


def document_key(tenant_id: UUID | str, document_id: UUID | str, extension: str = "") -> str:
    """The one place a storage key is spelled, so every caller agrees."""
    return f"{tenant_id}/{document_id}{extension}"
