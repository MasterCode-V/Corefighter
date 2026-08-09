"""Create a minimal WordPress draft to verify posting works."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from app.integrations.wordpress_client import WordPressClient, WordPressError


def _load_env() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


async def main() -> None:
    _load_env()
    client = WordPressClient(
        os.getenv("WORDPRESS_BASE_URL", "https://www.buyersbox.co.jp"),
        os.getenv("WORDPRESS_USERNAME", "corefighter-api"),
        os.getenv("WORDPRESS_APP_PASSWORD", ""),
    )
    me = await client._request("GET", "/users/me")
    print("AUTH_OK", me.get("name"), me.get("id"))
    post = await client.create_post(
        {
            "title": "CORE FIGHTER 接続テスト（下書き）",
            "content": "<p>これは CORE FIGHTER からの下書き投稿テストです。公開しないでください。</p>",
            "status": "draft",
        }
    )
    print("DRAFT_OK", post.get("id"), post.get("link") or post.get("guid"))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except WordPressError as exc:
        print("FAIL", str(exc)[:300])
        raise
