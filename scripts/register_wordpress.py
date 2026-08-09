"""Register / update WordPress site credentials for every store.

Usage (from project root, with .env loaded by pydantic settings via imports):

    python -m scripts.register_wordpress

Reads:
    WORDPRESS_BASE_URL
    WORDPRESS_USERNAME
    WORDPRESS_APP_PASSWORD
    WORDPRESS_DEFAULT_CATEGORY_ID (optional)
    WORDPRESS_DEFAULT_AUTHOR_ID (optional)
"""
from __future__ import annotations

import asyncio
import os

from sqlalchemy import select

from app.core.database import AsyncSessionFactory, engine
from app.core.logging import get_logger
from app.core.security import encrypt_secret
from app.integrations.wordpress_client import WordPressClient, WordPressError
from app.models import Store, WordPressSite

logger = get_logger("register_wordpress")


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


async def register() -> None:
    base_url = _env("WORDPRESS_BASE_URL", "https://www.buyersbox.co.jp")
    username = _env("WORDPRESS_USERNAME")
    app_password = _env("WORDPRESS_APP_PASSWORD")
    if not username or not app_password:
        raise SystemExit(
            "Set WORDPRESS_USERNAME and WORDPRESS_APP_PASSWORD in the environment / .env"
        )

    cat = _env("WORDPRESS_DEFAULT_CATEGORY_ID")
    author = _env("WORDPRESS_DEFAULT_AUTHOR_ID")
    default_category_id = int(cat) if cat.isdigit() else None
    default_author_id = int(author) if author.isdigit() else None

    # Connectivity probe (best-effort; XServer WAF may block some IPs).
    client = WordPressClient(base_url, username, app_password)
    try:
        me = await client._request("GET", "/users/me")
        logger.info("WordPress auth OK as %s (id=%s)", me.get("name"), me.get("id"))
    except WordPressError as exc:
        # Truncate to avoid logging huge WAF HTML bodies / encoding issues.
        logger.warning("WordPress auth probe failed (will still save credentials): %s", str(exc)[:200])

    encrypted = encrypt_secret(app_password.replace(" ", ""))

    async with AsyncSessionFactory() as db:
        stores = list((await db.execute(select(Store).where(Store.is_active.is_(True)))).scalars())
        if not stores:
            raise SystemExit("No stores found — run python -m scripts.seed first")

        for store in stores:
            existing = await db.execute(
                select(WordPressSite).where(WordPressSite.store_id == store.id).limit(1)
            )
            site = existing.scalar_one_or_none()
            if site is None:
                site = WordPressSite(
                    store_id=store.id,
                    name=f"{store.name} WP",
                    base_url=base_url,
                    username=username,
                    encrypted_app_password=encrypted,
                    default_category_id=default_category_id,
                    default_author_id=default_author_id,
                    is_active=True,
                )
                db.add(site)
                logger.info("Created WordPress site for store %s", store.code)
            else:
                site.base_url = base_url
                site.username = username
                site.encrypted_app_password = encrypted
                site.default_category_id = default_category_id
                site.default_author_id = default_author_id
                site.is_active = True
                logger.info("Updated WordPress site for store %s", store.code)

        await db.commit()
    await engine.dispose()
    logger.info("WordPress registration complete for %s store(s).", len(stores))


if __name__ == "__main__":
    # Load .env into os.environ for this script (Settings also loads it for ENCRYPTION_KEY).
    from pathlib import Path

    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)

    # Ensure encryption settings are imported after env load.
    from app.core.config import settings  # noqa: F401

    asyncio.run(register())
