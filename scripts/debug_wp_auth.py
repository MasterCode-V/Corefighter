"""Debug WordPress Basic-auth delivery (Authorization header / routes)."""
from __future__ import annotations

import asyncio
import base64
import os
from pathlib import Path

import httpx


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
    user = os.getenv("WORDPRESS_USERNAME", "corefighter-api")
    pw = (os.getenv("WORDPRESS_APP_PASSWORD") or "").replace(" ", "")
    token = base64.b64encode(f"{user}:{pw}".encode()).decode()
    print("user", user, "pw_len", len(pw))

    urls = [
        "https://www.buyersbox.co.jp/wp-json/wp/v2/users/me",
        "https://www.buyersbox.co.jp/?rest_route=/wp/v2/users/me",
        "https://buyersbox.co.jp/wp-json/wp/v2/users/me",
    ]
    header_sets = [
        {"Authorization": f"Basic {token}", "User-Agent": "CORE-FIGHTER/1.0", "Accept": "application/json"},
        {
            "Authorization": f"Basic {token}",
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        },
    ]

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        for url in urls:
            for headers in header_sets:
                resp = await client.get(url, headers=headers)
                print(resp.status_code, url, resp.text[:140].replace("\n", " "))


if __name__ == "__main__":
    asyncio.run(main())
