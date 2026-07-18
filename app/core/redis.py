"""ARQ Redis pool helpers for enqueuing background jobs."""
from __future__ import annotations

from typing import Optional

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import settings


def get_redis_settings() -> RedisSettings:
    return RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        database=settings.REDIS_DB,
        password=settings.REDIS_PASSWORD or None,
    )


_pool: Optional[ArqRedis] = None


async def get_arq_pool() -> ArqRedis:
    """Return a shared ARQ pool (lazy singleton)."""
    global _pool
    if _pool is None:
        _pool = await create_pool(get_redis_settings())
    return _pool


async def close_arq_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
