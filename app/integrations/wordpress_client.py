"""WordPress REST API client (workflows 11-15).

Uses application passwords over HTTP Basic auth against the WP REST API v2.

Note: Some hosts (including XSERVER) strip the Authorization header on
``/wp-json/...`` pretty permalinks. We therefore call REST via
``/?rest_route=/wp/v2/...`` which preserves Basic auth.
"""
from __future__ import annotations

import base64
import re
from typing import Any, List, Optional
from urllib.parse import parse_qsl, urlencode

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


def _ascii_media_filename(filename: str) -> str:
    """HTTP Content-Disposition must be Latin-1/ASCII.

    Original camera names often include Japanese (e.g. スクリーンショット.png).
    Putting those in the header raises:
    ``'ascii' codec can't encode characters ... ordinal not in range(128)``.
    """
    name = (filename or "image.jpg").replace("\\", "/").split("/")[-1]
    name = name.replace('"', "").replace("\r", "").replace("\n", "")
    ext = "jpg"
    if "." in name:
        maybe = name.rsplit(".", 1)[-1].lower()
        if re.fullmatch(r"[a-z0-9]{1,8}", maybe):
            ext = maybe
        stem = name.rsplit(".", 1)[0]
    else:
        stem = name
    stem = _UNSAFE_FILENAME.sub("_", stem).strip("._") or "image"
    return f"{stem[:80]}.{ext}"


class WordPressError(Exception):
    pass


class WordPressClient:
    def __init__(self, base_url: str, username: str, app_password: str) -> None:
        self._base = base_url.rstrip("/")
        # Application passwords are often copied with spaces; WordPress accepts either.
        self._username = username
        self._password = app_password.replace(" ", "")
        self._headers = {
            "User-Agent": "CORE-FIGHTER/1.0 (+https://github.com/MasterCode-V/Corefighter)",
            "Accept": "application/json",
        }

    def _auth_headers(self) -> dict[str, str]:
        token = base64.b64encode(f"{self._username}:{self._password}".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    def _rest_url(self, route: str, query: Optional[dict[str, Any]] = None) -> str:
        """Build ``/?rest_route=/wp/v2/...`` (or another namespace) URL."""
        if not route.startswith("/"):
            route = "/" + route
        params: dict[str, Any] = {"rest_route": route}
        if query:
            params.update({k: v for k, v in query.items() if v is not None})
        return f"{self._base}/?{urlencode(params, doseq=True)}"

    def _wp_v2_url(self, path: str) -> str:
        """Convert a path like ``/posts/1?context=edit`` into a rest_route URL."""
        if path.startswith("http"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        route_path = path
        query: dict[str, Any] = {}
        if "?" in path:
            route_path, qs = path.split("?", 1)
            for key, value in parse_qsl(qs, keep_blank_values=True):
                query[key] = value
        return self._rest_url(f"/wp/v2{route_path}", query)

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        url = path if path.startswith("http") else self._wp_v2_url(path)
        headers = {
            **self._headers,
            **self._auth_headers(),
            **(kwargs.pop("headers", {}) or {}),
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.request(method, url, headers=headers, **kwargs)
        if resp.status_code >= 400:
            raise WordPressError(
                f"WordPress {method} {path} failed: {resp.status_code} {resp.text[:500]}"
            )
        if resp.content:
            return resp.json()
        return None

    # ---- Media ----
    async def upload_media(self, data: bytes, filename: str, content_type: str) -> dict:
        safe_name = _ascii_media_filename(filename)
        headers = {
            "Content-Disposition": f'attachment; filename="{safe_name}"',
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
        url = self._rest_url("/wp/v2/posts", params)
        headers = {**self._headers, **self._auth_headers()}
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code >= 400:
            raise WordPressError(f"list_posts failed: {resp.status_code} {resp.text[:300]}")
        total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
        return resp.json(), total_pages

    async def search_posts(
        self,
        *,
        search: Optional[str] = None,
        categories: Optional[List[int]] = None,
        per_page: int = 20,
        exclude_id: Optional[int] = None,
    ) -> List[dict]:
        """Search published WordPress posts (used for manual related-article picker)."""
        params: dict[str, Any] = {
            "status": "publish",
            "per_page": min(max(per_page, 1), 50),
            "orderby": "date",
            "order": "desc",
            "_embed": "wp:featuredmedia",
        }
        if search:
            params["search"] = search
        if categories:
            params["categories"] = ",".join(str(c) for c in categories)
        url = self._rest_url("/wp/v2/posts", params)
        headers = {**self._headers, **self._auth_headers()}
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code >= 400:
            raise WordPressError(f"search_posts failed: {resp.status_code} {resp.text[:300]}")
        rows = resp.json() if resp.content else []
        if not isinstance(rows, list):
            return []
        if exclude_id:
            rows = [r for r in rows if r.get("id") != exclude_id]
        return rows

    # ---- Taxonomy ----
    async def list_categories(self, hide_empty: bool = False) -> list[dict]:
        page = 1
        all_rows: list[dict] = []
        while True:
            flag = "true" if hide_empty else "false"
            rows = await self._request(
                "GET", f"/categories?per_page=100&page={page}&hide_empty={flag}"
            )
            if not rows:
                break
            all_rows.extend(rows)
            if len(rows) < 100:
                break
            page += 1
        return all_rows

    async def ensure_category(self, name: str) -> int:
        # Prefer known buyersbox catalog IDs to avoid creating duplicates.
        from app.services.wordpress_categories import category_id_for_name

        known = category_id_for_name(name)
        if known is not None:
            return known
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

    async def list_tags(self, search: Optional[str] = None, limit: int = 100) -> List[dict]:
        """Return existing WordPress tags (paginated, optional search)."""
        per_page = min(max(limit, 1), 100)
        query = {
            "per_page": str(per_page),
            "orderby": "count",
            "order": "desc",
            "hide_empty": "false",
        }
        if search:
            query["search"] = search
        path = "/tags?" + urlencode(query)
        rows = await self._request("GET", path)
        return list(rows or [])[:limit]

    # ---- YARPP related posts (Yet Another Related Posts Plugin) ----
    async def get_related_posts(self, post_id: int, limit: int = 4) -> List[dict]:
        """Fetch the related posts YARPP computes for a given post.

        Prefers rest_route form so Authorization survives host proxies.
        """
        url = self._rest_url(f"/yarpp/v1/related/{post_id}", {"limit": limit, "_embed": "1"})
        headers = {**self._headers, **self._auth_headers()}
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code == 404:
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
                thumb = (
                    details.get("medium_large")
                    or details.get("large")
                    or details.get("medium")
                    or details.get("thumbnail")
                    or {}
                )
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
