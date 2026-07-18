"""Public media proxy — streams objects from MinIO so the frontend can show
images without relying on anonymous MinIO / CORS."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.core.storage import storage

router = APIRouter()


@router.get("/{object_key:path}")
async def get_media(object_key: str) -> Response:
    if not object_key or ".." in object_key:
        raise HTTPException(status_code=400, detail="Invalid media key")
    try:
        data = await storage.download_bytes(object_key)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail="Media not found") from exc

    content_type = "application/octet-stream"
    lower = object_key.lower()
    if lower.endswith((".jpg", ".jpeg")):
        content_type = "image/jpeg"
    elif lower.endswith(".png"):
        content_type = "image/png"
    elif lower.endswith(".webp"):
        content_type = "image/webp"
    elif lower.endswith(".gif"):
        content_type = "image/gif"

    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
