from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Enum as SAEnum, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import LogLevel
from app.models.base import Base, TimestampMixin, UUIDMixin


class ActivityLog(UUIDMixin, TimestampMixin, Base):
    """Audit / activity / error log used for the history views in the dashboard."""

    __tablename__ = "activity_logs"

    level: Mapped[LogLevel] = mapped_column(
        SAEnum(LogLevel, name="log_level"), default=LogLevel.INFO, nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(64), default="", index=True)
    message: Mapped[str] = mapped_column(Text, default="")

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    store_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    article_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)

    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
