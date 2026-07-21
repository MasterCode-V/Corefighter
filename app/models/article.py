from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import ArticleStatus
from app.models.base import Base, TimestampMixin, UUIDMixin


class Article(UUIDMixin, TimestampMixin, Base):
    """An article tied to a purchase. Holds lifecycle status + WordPress mapping."""

    __tablename__ = "articles"

    purchase_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("purchases.id", ondelete="CASCADE"),
        unique=True, nullable=False,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[ArticleStatus] = mapped_column(
        SAEnum(ArticleStatus, name="article_status"),
        default=ArticleStatus.DRAFT, nullable=False, index=True,
    )

    current_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("article_versions.id", ondelete="SET NULL", use_alter=True,
                   name="fk_article_current_version"),
        nullable=True,
    )
    latest_similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ---- WordPress mapping ----
    wordpress_site_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("wordpress_sites.id", ondelete="SET NULL"), nullable=True
    )
    wordpress_post_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    published_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    published_at: Mapped[Optional["DateTime"]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ---- Approval bookkeeping ----
    submitted_by: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    review_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    purchase: Mapped["Purchase"] = relationship(back_populates="article")  # noqa: F821
    versions: Mapped[List["ArticleVersion"]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        foreign_keys="ArticleVersion.article_id",
        order_by="ArticleVersion.version_no",
    )
    current_version: Mapped[Optional["ArticleVersion"]] = relationship(
        foreign_keys=[current_version_id], post_update=True, viewonly=True
    )


class ArticleVersion(UUIDMixin, TimestampMixin, Base):
    """Immutable snapshot of a generated/edited article. History is preserved."""

    __tablename__ = "article_versions"
    __table_args__ = (
        UniqueConstraint("article_id", "version_no", name="uq_article_version_no"),
    )

    article_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    title: Mapped[str] = mapped_column(String(512), default="")
    introduction: Mapped[str] = mapped_column(Text, default="")
    headings: Mapped[list] = mapped_column(JSONB, default=list)
    # body = only the AI-written variable content (used for similarity so the
    # fixed header/footer boilerplate never inflates similarity scores).
    body: Mapped[str] = mapped_column(Text, default="")
    # rendered_html = full assembled article (fixed heading + thanks + image +
    # AI body + fixed footer). This is what is published to WordPress.
    rendered_html: Mapped[str] = mapped_column(Text, default="")
    excerpt: Mapped[str] = mapped_column(Text, default="")
    category_suggestion: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tag_suggestions: Mapped[list] = mapped_column(JSONB, default=list)

    # Provenance
    generated_by_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    regeneration_scope: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    regeneration_instruction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_manual_edit: Mapped[bool] = mapped_column(default=False)

    # Validation / similarity snapshots for this version
    validation_outcome: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    validation_result: Mapped[dict] = mapped_column(JSONB, default=dict)
    similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    article: Mapped["Article"] = relationship(
        back_populates="versions", foreign_keys=[article_id]
    )

    @property
    def full_text(self) -> str:
        parts = [self.title, self.introduction, self.body, self.excerpt]
        return "\n\n".join(p for p in parts if p)
