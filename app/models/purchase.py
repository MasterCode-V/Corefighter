from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import (
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import ImageType, PurchaseStatus
from app.models.base import Base, TimestampMixin, UUIDMixin


class Purchase(UUIDMixin, TimestampMixin, Base):
    """A purchase (buyback) record - the unit of work that becomes an article."""

    __tablename__ = "purchases"

    store_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    persona_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[PurchaseStatus] = mapped_column(
        SAEnum(PurchaseStatus, name="purchase_status"),
        default=PurchaseStatus.UNSTARTED,
        nullable=False,
    )

    # ---- Buyback header info (matches the store's paper form) ----
    purchase_date: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)   # 日付 e.g. 7/14
    purchase_method: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # 買取方法 店頭/出張
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)          # 個数
    quantity_unit: Mapped[str] = mapped_column(String(16), default="点", nullable=False)  # 台/点/本...

    # ---- Product information (AI-extracted and/or manually entered) ----
    manufacturer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    product_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    model_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    condition: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    characteristics: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)

    # Free-form optional info entered by staff + raw AI extraction payload.
    manual_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_info: Mapped[dict] = mapped_column(JSONB, default=dict)
    ai_extraction: Mapped[dict] = mapped_column(JSONB, default=dict)

    user_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    images: Mapped[List["PurchaseImage"]] = relationship(
        back_populates="purchase", cascade="all, delete-orphan"
    )
    products: Mapped[List["PurchaseProduct"]] = relationship(
        back_populates="purchase",
        cascade="all, delete-orphan",
        order_by="PurchaseProduct.sort_order",
    )
    article: Mapped[Optional["Article"]] = relationship(  # noqa: F821
        back_populates="purchase", uselist=False
    )


class PurchaseProduct(UUIDMixin, TimestampMixin, Base):
    """One product line inside a purchase.

    A single buyback can contain several distinct products. When a purchase has
    no product rows the legacy purchase-level columns are used as a single
    implicit product (see ``article_template.effective_products``).
    """

    __tablename__ = "purchase_products"

    purchase_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    manufacturer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    product_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    model_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    condition: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    characteristics: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    quantity_unit: Mapped[str] = mapped_column(String(16), default="点", nullable=False)
    price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)

    purchase: Mapped["Purchase"] = relationship(back_populates="products")


class PurchaseImage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "purchase_images"

    purchase_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False
    )
    image_type: Mapped[ImageType] = mapped_column(
        SAEnum(ImageType, name="image_type"), default=ImageType.DETAIL, nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), default="")
    content_type: Mapped[str] = mapped_column(String(128), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # Set once uploaded to WordPress media library.
    wordpress_media_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    purchase: Mapped["Purchase"] = relationship(back_populates="images")
