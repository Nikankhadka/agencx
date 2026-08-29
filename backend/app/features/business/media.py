"""Small Cloudinary Upload API adapter and safe external-media classifiers."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel

from app.shared.config import Settings, get_settings


class MediaUploadError(RuntimeError):
    """Cloudinary rejected or could not complete a media operation."""


@dataclass(frozen=True)
class UploadedMedia:
    type: str
    provider: str
    url: str
    public_id: str | None = None
    poster_url: str | None = None


class OfferingMedia(BaseModel):
    type: Literal["image", "video"]
    provider: Literal["cloudinary", "youtube", "vimeo"]
    url: str
    poster_url: str | None = None


def classify_url(url: str) -> tuple[str, str] | None:
    """Return a controlled provider/type pair for supported video hosts."""
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if host in {"youtube.com", "youtu.be", "youtube-nocookie.com"}:
        return "video", "youtube"
    if host in {"vimeo.com", "player.vimeo.com"}:
        return "video", "vimeo"
    return None


def _signature(params: dict[str, str], secret: str) -> str:
    canonical = "&".join(f"{key}={params[key]}" for key in sorted(params))
    return hashlib.sha1(f"{canonical}{secret}".encode()).hexdigest()


def _video_poster_url(url: str) -> str:
    """Ask Cloudinary for the first frame without embedding a video player."""
    stem, separator, _extension = url.rpartition(".")
    return f"{stem if separator else url}.jpg"


class Cloudinary:
    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None):
        self.settings = settings or get_settings()
        self.client = client

    def _configured(self) -> None:
        if not all(
            (
                self.settings.cloudinary_cloud_name,
                self.settings.cloudinary_api_key,
                self.settings.cloudinary_api_secret,
            )
        ):
            raise MediaUploadError("Cloudinary is not configured")

    @property
    def is_configured(self) -> bool:
        return bool(
            self.settings.cloudinary_cloud_name
            and self.settings.cloudinary_api_key
            and self.settings.cloudinary_api_secret
        )

    async def upload(
        self,
        *,
        data: bytes | str,
        resource_type: str,
        folder: str,
        filename: str = "upload",
    ) -> UploadedMedia:
        self._configured()
        timestamp = str(int(time.time()))
        params = {"folder": folder, "timestamp": timestamp}
        endpoint = (
            f"https://api.cloudinary.com/v1_1/{self.settings.cloudinary_cloud_name}/"
            f"{resource_type}/upload"
        )
        form = {
            **params,
            "api_key": self.settings.cloudinary_api_key,
            "signature": _signature(params, self.settings.cloudinary_api_secret),
        }
        files = {"file": (filename, data)} if isinstance(data, bytes) else None
        if isinstance(data, str):
            form["file"] = data
        client = self.client or httpx.AsyncClient(timeout=30.0)
        close = self.client is None
        try:
            response = await client.post(endpoint, data=form, files=files)
            if response.is_error:
                raise MediaUploadError(f"Cloudinary upload failed ({response.status_code})")
            payload = response.json()
            secure_url = str(payload["secure_url"])
            public_id = payload.get("public_id")
            detected_type = str(payload.get("resource_type") or resource_type)
            if detected_type not in {"image", "video"}:
                raise MediaUploadError("Cloudinary accepted an unsupported media type")
        except MediaUploadError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise MediaUploadError("Cloudinary upload failed") from exc
        finally:
            if close:
                await client.aclose()
        return UploadedMedia(
            type="video" if detected_type == "video" else "image",
            provider="cloudinary",
            url=secure_url,
            public_id=str(public_id) if public_id else None,
            poster_url=(_video_poster_url(secure_url) if detected_type == "video" else None),
        )

    async def delete(self, *, public_id: str, resource_type: str) -> None:
        self._configured()
        timestamp = str(int(time.time()))
        params = {"public_id": public_id, "timestamp": timestamp}
        endpoint = (
            f"https://api.cloudinary.com/v1_1/{self.settings.cloudinary_cloud_name}/"
            f"{resource_type}/destroy"
        )
        form = {
            **params,
            "api_key": self.settings.cloudinary_api_key,
            "signature": _signature(params, self.settings.cloudinary_api_secret),
        }
        client = self.client or httpx.AsyncClient(timeout=15.0)
        close = self.client is None
        try:
            response = await client.post(endpoint, data=form)
            if response.is_error:
                raise MediaUploadError(f"Cloudinary delete failed ({response.status_code})")
        except httpx.HTTPError as exc:
            raise MediaUploadError("Cloudinary delete failed") from exc
        finally:
            if close:
                await client.aclose()
