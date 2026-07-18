"""WordPress REST API client (workflows 11-15).

Uses application passwords over HTTP Basic auth against the WP REST API v2.
"""
from __future__ import annotations

from typing import Any, List, Optional

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)


class WordPressError(Exception):
    pass


class WordPressClient:
    def __init__(self, base_url: str, username: str, app_password: str) -> None:
        self._base = base_url.rstrip("/")
        self._auth = (username, app_password)

    @property
    def _api(self) -> str:
        return f"{self._base}/wp-json/wp/v2"

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        url = path if path.startswith("http") else f"{self._api}{path}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.request(method, url, auth=self._auth, **kwargs)
        if resp.status_code >= 400:
            raise WordPressError(
                f"WordPress {method} {path} failed: {resp.status_code} {resp.text[:500]}"
            )
        if resp.content:
            return resp.json()
        return None

    # ---- Media ----
    async def upload_media(self, data: bytes, filename: str, content_type: str) -> dict:
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": content_type or "application/octet-stream",
        }
        return await self._request("POST", "/media", content=data, headers=headers)

    # ---- Posts ----
    async def get_post(self, post_id: int) -> Optional[dict]:
        try:
            return await self._request("GET", f"/posts/{post_id}?context=edit")
        except WordPressError:
            return None

    async def create_post(self, payload: dict) -> dict:
        return await self._request("POST", "/posts", json=payload)

    async def update_post(self, post_id: int, payload: dict) -> dict:
        return await self._request("POST", f"/posts/{post_id}", json=payload)

    async def list_posts(
        self, status: str = "publish", page: int = 1, per_page: int = 50,
        modified_after: Optional[str] = None,
    ) -> tuple[list, int]:
        params: dict[str, Any] = {
            "status": status, "page": page, "per_page": per_page,
            "context": "edit", "orderby": "modified", "order": "desc",
        }
        if modified_after:
            params["modified_after"] = modified_after
        url = f"{self._api}/posts"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url, auth=self._auth, params=params)
        if resp.status_code >= 400:
            raise WordPressError(f"list_posts failed: {resp.status_code} {resp.text[:300]}")
        total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
        return resp.json(), total_pages

    # ---- Taxonomy ----
    async def ensure_category(self, name: str) -> int:
        existing = await self._request("GET", f"/categories?search={name}")
        for cat in existing or []:
            if cat.get("name", "").lower() == name.lower():
                return cat["id"]
        created = await self._request("POST", "/categories", json={"name": name})
        return created["id"]

    async def ensure_tags(self, names: List[str]) -> List[int]:
        ids: List[int] = []
        for name in names:
            if not name:
                continue
            existing = await self._request("GET", f"/tags?search={name}")
            match = next(
                (t["id"] for t in (existing or []) if t.get("name", "").lower() == name.lower()),
                None,
            )
            if match is None:
                created = await self._request("POST", "/tags", json={"name": name})
                match = created["id"]
            ids.append(match)
        return ids

    # ---- YARPP related posts (Yet Another Related Posts Plugin) ----
    async def get_related_posts(self, post_id: int, limit: int = 4) -> List[dict]:
        """Fetch the related posts YARPP computes for a given post.

        Endpoint: GET /wp-json/yarpp/v1/related/{id}
        Requires "Display related posts in REST API" enabled in YARPP settings.
        Returns the same posts (quantity/order) shown on the live site.
        """
        url = f"{self._base}/wp-json/yarpp/v1/related/{post_id}"
        params = {"limit": limit, "_embed": "1"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url, auth=self._auth, params=params)
        if resp.status_code == 404:
            # No related posts, or YARPP REST not enabled / post not found.
            return []
        if resp.status_code >= 400:
            raise WordPressError(
                f"YARPP related for {post_id} failed: {resp.status_code} {resp.text[:300]}"
            )
        data = resp.json()
        return data if isinstance(data, list) else []

    @staticmethod
    def normalize_related(items: List[dict]) -> List[dict]:
        """Flatten YARPP/WP post objects into simple cards (id/title/link/date/thumbnail)."""
        result: List[dict] = []
        for item in items or []:
            title = item.get("title")
            if isinstance(title, dict):
                title = title.get("rendered", "")
            thumbnail = None
            embedded = item.get("_embedded") or {}
            media = embedded.get("wp:featuredmedia") or []
            if media and isinstance(media, list):
                m0 = media[0] or {}
                details = (m0.get("media_details") or {}).get("sizes") or {}
                thumb = details.get("medium") or details.get("thumbnail") or {}
                thumbnail = thumb.get("source_url") or m0.get("source_url")
            result.append(
                {
                    "id": item.get("id"),
                    "title": title or "",
                    "link": item.get("link", ""),
                    "date": item.get("date", ""),
                    "thumbnail": thumbnail,
                    "score": item.get("score") or item.get("yarpp_score"),
                }
            )
        return result
