from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class PurchaseMethod(UUIDMixin, TimestampMixin, Base):
    """Configurable purchase channel (店頭 / 出張 / 宅配 …).

    When ``linked_store_id`` is set, selecting this method auto-assigns the
    article to that store (e.g. 出張 → デリパワ, 宅配 → 宅配買取).
    """

    __tablename__ = "purchase_methods"

    label: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_area: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    linked_store_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("stores.id", ondelete="SET NULL"), nullable=True
    )

    linked_store: Mapped[Optional["Store"]] = relationship(  # noqa: F821
        foreign_keys=[linked_store_id]
    )
