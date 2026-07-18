from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import JobStatus, JobType
from app.models.base import Base, TimestampMixin, UUIDMixin


class Job(UUIDMixin, TimestampMixin, Base):
    """Background job. The DB row is the source of truth for status/history;
    Redis (ARQ) is only the transport. Follows the unified status flow (16)."""

    __tablename__ = "jobs"

    job_type: Mapped[JobType] = mapped_column(
        SAEnum(JobType, name="job_type"), nullable=False, index=True
    )
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, name="job_status"),
        default=JobStatus.PENDING, nullable=False, index=True,
    )

    # Optional relations to the entities the job operates on.
    purchase_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("purchases.id", ondelete="CASCADE"), nullable=True
    )
    article_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=True
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)

    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    result: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    queue_name: Mapped[str] = mapped_column(String(64), default="default")

    # ARQ job id for correlation / cancellation.
    arq_job_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
