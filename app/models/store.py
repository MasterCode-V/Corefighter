from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Store(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "stores"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    address: Mapped[str] = mapped_column(String(512), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Store-specific article template overrides (label, area, footer html, etc.).
    # Merged over the global defaults in app.services.article_template.
    article_config: Mapped[dict] = mapped_column(JSONB, default=dict)

    users: Mapped[List["User"]] = relationship(back_populates="store")  # noqa: F821
    personas: Mapped[List["Persona"]] = relationship(  # noqa: F821
        back_populates="store", cascade="all, delete-orphan"
    )
    wordpress_sites: Mapped[List["WordPressSite"]] = relationship(
        back_populates="store", cascade="all, delete-orphan"
    )


class WordPressSite(UUIDMixin, TimestampMixin, Base):
    """WordPress connection configuration bound to a store."""

    __tablename__ = "wordpress_sites"

    store_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), default="")
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    # WordPress application password, stored encrypted at rest.
    encrypted_app_password: Mapped[str] = mapped_column(Text, nullable=False)
    default_category_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    default_author_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    store: Mapped["Store"] = relationship(back_populates="wordpress_sites")
