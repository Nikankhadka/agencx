from __future__ import annotations

import httpx

from app.features.business.media import Cloudinary, classify_url
from app.shared.config import Settings


def _settings() -> Settings:
    return Settings(
        cloudinary_cloud_name="demo-cloud",
        cloudinary_api_key="123456789012345",
        cloudinary_api_secret="secret-value-123",
    )


def test_classify_supported_video_hosts_only() -> None:
    assert classify_url("https://youtu.be/example") == ("video", "youtube")
    assert classify_url("https://vimeo.com/123") == ("video", "vimeo")
    assert classify_url("https://example.com/photo.jpg") is None


async def test_signed_upload_and_delete_use_server_credentials() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/upload"):
            return httpx.Response(
                200,
                json={
                    "secure_url": "https://res.cloudinary.com/demo/image/upload/x.jpg",
                    "public_id": "tenant/photo",
                },
            )
        return httpx.Response(200, json={"result": "ok"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = Cloudinary(settings=_settings(), client=client)
    uploaded = await adapter.upload(data=b"image", resource_type="image", folder="tenant/1")
    await adapter.delete(public_id="tenant/photo", resource_type="image")
    await client.aclose()

    assert uploaded.provider == "cloudinary"
    assert uploaded.url.startswith("https://res.cloudinary.com/")
    assert len(requests) == 2
    assert requests[0].url.host == "api.cloudinary.com"
    assert "api_key" not in str(requests[0].url)
    assert requests[0].headers["content-type"].startswith("multipart/form-data")


async def test_auto_upload_uses_cloudinary_resource_type_and_video_poster() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "secure_url": "https://res.cloudinary.com/demo/video/upload/x.mp4",
                "public_id": "tenant/video",
                "resource_type": "video",
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = Cloudinary(settings=_settings(), client=client)
    uploaded = await adapter.upload(
        data="https://example.com/media/recording",
        resource_type="auto",
        folder="tenant/1",
    )
    await client.aclose()

    assert requests[0].url.path.endswith("/auto/upload")
    assert uploaded.type == "video"
    assert uploaded.poster_url == "https://res.cloudinary.com/demo/video/upload/x.jpg"
