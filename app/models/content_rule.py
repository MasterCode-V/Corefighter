from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import ContentRuleType
from app.models.base import Base, TimestampMixin, UUIDMixin


class ContentRule(UUIDMixin, TimestampMixin, Base):
    """Prohibited words/contexts, brand rules and structure requirements.

    Global rules have store_id = NULL (common brand rules); store rules override.
    """

    __tablename__ = "content_rules"

    store_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=True
    )
    rule_type: Mapped[ContentRuleType] = mapped_column(
        SAEnum(ContentRuleType, name="content_rule_type"), nullable=False
    )
    value: Mapped[str] = mapped_column(String(512), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
