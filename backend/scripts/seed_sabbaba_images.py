"""One-off upload of the Sabbaba demo photos to Cloudinary.

Reads a name-to-file map (offering name -> image file, plus ``__cover__``) and
the downloaded photos, uploads each under a deterministic ``demo/sabbaba/<slug>``
public id with overwrite (so a re-run replaces files instead of orphaning
them), and writes ``seeds/sabbaba/images.json`` for the offline seed to read.

    python -m scripts.seed_sabbaba_images --src <photo dir> --map <map.json>

The map is ``{"Offering name": "<file name in --src>", "__cover__": "<file>"}``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from pathlib import Path

import httpx

from app.features.business.media import MediaUploadError, _signature
from app.shared.config import get_settings

OUT = Path(__file__).resolve().parent.parent / "seeds" / "sabbaba" / "images.json"
FOLDER = "demo/sabbaba"


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


async def _upload(client: httpx.AsyncClient, path: Path, public_id: str) -> dict[str, str]:
    settings = get_settings()
    data = await asyncio.to_thread(path.read_bytes)
    params = {
        "overwrite": "true",
        "public_id": public_id,
        "timestamp": str(int(time.time())),
    }
    response = await client.post(
        f"https://api.cloudinary.com/v1_1/{settings.cloudinary_cloud_name}/image/upload",
        data={
            **params,
            "api_key": settings.cloudinary_api_key,
            "signature": _signature(params, settings.cloudinary_api_secret),
        },
        files={"file": (path.name, data)},
    )
    if response.is_error:
        raise MediaUploadError(f"{public_id}: upload failed ({response.status_code})")
    payload = response.json()
    return {"url": payload["secure_url"], "public_id": payload["public_id"]}


async def main(src: Path, mapping: dict[str, str]) -> None:
    settings = get_settings()
    if not (
        settings.cloudinary_cloud_name
        and settings.cloudinary_api_key
        and settings.cloudinary_api_secret
    ):
        raise RuntimeError("Cloudinary is not configured")
    result: dict[str, dict[str, str]] = {}
    async with httpx.AsyncClient(timeout=60.0) as client:
        for name, file in mapping.items():
            public_id = f"{FOLDER}/{'cover' if name == '__cover__' else _slug(name)}"
            result[name] = await _upload(client, src / file, public_id)
            print(f"uploaded {name} -> {result[name]['public_id']}")
    cover = result.pop("__cover__")
    manifest = json.dumps({"cover": cover, "offerings": result}, indent=2, ensure_ascii=False)
    await asyncio.to_thread(OUT.write_text, manifest + "\n")
    print(f"wrote {OUT} ({len(result)} offerings + cover)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", type=Path, required=True)
    parser.add_argument("--map", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(main(args.src, json.loads(args.map.read_text())))
