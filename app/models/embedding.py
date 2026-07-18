from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.models.base import Base, TimestampMixin, UUIDMixin

EMBEDDING_DIM = settings.OPENAI_EMBEDDING_DIM


class PublishedCorpus(UUIDMixin, TimestampMixin, Base):
    """Corpus of published articles used as the similarity comparison target.

    Populated by the historical WordPress synchronization worker (workflow 15)
    and after each successful publication.
    """

    __tablename__ = "published_corpus"
    __table_args__ = (
        UniqueConstraint(
            "wordpress_site_id", "wordpress_post_id", name="uq_corpus_wp_post"
        ),
    )

    source: Mapped[str] = mapped_column(String(32), default="wordpress")  # wordpress|local
    wordpress_site_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("wordpress_sites.id", ondelete="SET NULL"), nullable=True
    )
    wordpress_post_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    article_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("articles.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(1024), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    normalized_content: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    embeddings: Mapped[List["CorpusEmbedding"]] = relationship(
        back_populates="corpus", cascade="all, delete-orphan"
    )


class CorpusEmbedding(UUIDMixin, Base):
    """Chunk-level embeddings for a published corpus entry (pgvector)."""

    __tablename__ = "corpus_embeddings"

    corpus_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("published_corpus.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text, default="")
    embedding: Mapped[list] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    corpus: Mapped["PublishedCorpus"] = relationship(back_populates="embeddings")
