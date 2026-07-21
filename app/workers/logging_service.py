"""Helper to persist activity/error logs from workers and services."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import LogLevel
from app.models import ActivityLog


async def write_log(
    db: AsyncSession,
    *,
    level: LogLevel,
    category: str,
    message: str,
    article_id: Optional[uuid.UUID] = None,
    job_id: Optional[uuid.UUID] = None,
    store_id: Optional[uuid.UUID] = None,
    payload: Optional[dict] = None,
) -> None:
    db.add(
        ActivityLog(
            level=level,
            category=category,
            message=message,
            article_id=article_id,
            job_id=job_id,
            store_id=store_id,
            payload=payload or {},
        )
    )
