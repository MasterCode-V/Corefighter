"""Create the pgvector extension, all tables and vector indexes.

Usage:  python -m scripts.init_db
This is a quick-start alternative to running Alembic migrations.
"""
from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.core.database import engine
from app.core.logging import get_logger
from app.models import Base  # noqa: F401 - registers all tables

logger = get_logger("init_db")

VECTOR_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS ix_corpus_embeddings_vector
ON corpus_embeddings
USING hnsw (embedding vector_cosine_ops);
"""

# Idempotent column additions so existing databases (created before these
# fields were added) get upgraded without a full Alembic migration.
UPGRADE_SQL = [
    "ALTER TABLE stores ADD COLUMN IF NOT EXISTS article_config JSONB DEFAULT '{}'::jsonb",
    "ALTER TABLE purchases ADD COLUMN IF NOT EXISTS purchase_date VARCHAR(64)",
    "ALTER TABLE purchases ADD COLUMN IF NOT EXISTS purchase_method VARCHAR(32)",
    "ALTER TABLE purchases ADD COLUMN IF NOT EXISTS quantity INTEGER DEFAULT 1 NOT NULL",
    "ALTER TABLE purchases ADD COLUMN IF NOT EXISTS quantity_unit VARCHAR(16) DEFAULT '点' NOT NULL",
    "ALTER TABLE article_versions ADD COLUMN IF NOT EXISTS rendered_html TEXT DEFAULT ''",
]


async def init() -> None:
    async with engine.begin() as conn:
        logger.info("Ensuring pgvector extension...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        logger.info("Creating tables...")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Applying idempotent column upgrades...")
        for stmt in UPGRADE_SQL:
            try:
                await conn.execute(text(stmt))
            except Exception as exc:  # pragma: no cover
                logger.warning("Upgrade skipped (%s): %s", stmt[:60], exc)
        logger.info("Creating vector index...")
        try:
            await conn.execute(text(VECTOR_INDEX_SQL))
        except Exception as exc:  # pragma: no cover
            logger.warning("Could not create HNSW index (continuing): %s", exc)
    await engine.dispose()
    logger.info("Database initialization complete.")


if __name__ == "__main__":
    asyncio.run(init())
