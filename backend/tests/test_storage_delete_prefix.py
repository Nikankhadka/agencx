"""SupabaseStorage.delete_prefix against a stubbed Storage API.

Offboarding (T-031) deletes everything under ``{tenant_id}/``, so the listing has
to page: the API returns 100 names at a time and a tenant can own more.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from app.shared.storage import LocalStorage, SupabaseStorage

TENANT = "11111111-1111-1111-1111-111111111111"


def _storage(objects: list[str]) -> tuple[SupabaseStorage, list[str]]:
    """A storage whose bucket holds ``objects`` (names inside the tenant folder).

    Returns it with the list every DELETE request appends its keys to.
    """
    deleted: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if request.method == "POST":
            page = objects[body["offset"] : body["offset"] + body["limit"]]
            return httpx.Response(200, json=[{"name": name} for name in page])
        deleted.extend(body["prefixes"])
        return httpx.Response(200, json=[])

    storage = SupabaseStorage(base_url="http://storage.test", bucket="up", service_role_key="k")
    storage._client = httpx.AsyncClient(
        base_url="http://storage.test/storage/v1", transport=httpx.MockTransport(handler)
    )
    return storage, deleted


async def test_the_whole_tenant_folder_goes_even_past_one_page() -> None:
    names = [f"doc-{n:03d}.pdf" for n in range(250)]
    storage, deleted = _storage(names)

    await storage.delete_prefix(f"{TENANT}/")

    assert sorted(deleted) == sorted(f"{TENANT}/{n}" for n in names)


async def test_a_document_prefix_only_takes_that_documents_files() -> None:
    storage, deleted = _storage(["doc-1.pdf", "doc-1.png", "doc-2.pdf"])

    await storage.delete_prefix(f"{TENANT}/doc-1")

    assert sorted(deleted) == [f"{TENANT}/doc-1.pdf", f"{TENANT}/doc-1.png"]


async def test_an_empty_folder_sends_no_delete() -> None:
    storage, deleted = _storage([])

    await storage.delete_prefix(f"{TENANT}/")

    assert deleted == []


async def test_local_storage_removes_the_whole_tenant_folder_and_only_that_one(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(str(tmp_path))
    await storage.put(f"{TENANT}/doc-1.pdf", b"a")
    await storage.put(f"{TENANT}/doc-2.pdf", b"b")
    await storage.put("22222222-2222-2222-2222-222222222222/doc-1.pdf", b"c")

    await storage.delete_prefix(f"{TENANT}/")

    assert not (tmp_path / TENANT).exists()
    assert await storage.get("22222222-2222-2222-2222-222222222222/doc-1.pdf") == b"c"
    # A tenant that never uploaded anything is a no-op, not an error.
    await storage.delete_prefix(f"{TENANT}/")
