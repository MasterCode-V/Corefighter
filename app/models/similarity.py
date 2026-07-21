from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class SimilarityResult(UUIDMixin, TimestampMixin, Base):
    """Result of a similarity check for a specific article version (workflow 7)."""

    __tablename__ = "similarity_results"

    article_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    article_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("article_versions.id", ondelete="CASCADE"), nullable=False
    )

    similarity_score: Mapped[float] = mapped_column(Float, default=0.0)
    semantic_score: Mapped[float] = mapped_column(Float, default=0.0)
    text_score: Mapped[float] = mapped_column(Float, default=0.0)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)

    # [{corpus_id, wordpress_post_id, title, score}, ...]
    most_similar: Mapped[list] = mapped_column(JSONB, default=list)
    repeated_sections: Mapped[list] = mapped_column(JSONB, default=list)
