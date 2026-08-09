from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import Boolean, Column, Enum as SAEnum, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import UserRole
from app.models.base import Base, TimestampMixin, UUIDMixin

user_personas = Table(
    "user_personas",
    Base.metadata,
    Column(
        "user_id",
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "persona_id",
        PG_UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role"), nullable=False, default=UserRole.STORE_STAFF
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Store-scoped users (managers / staff) belong to a single store.
    store_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("stores.id", ondelete="SET NULL"), nullable=True
    )
    store: Mapped[Optional["Store"]] = relationship(back_populates="users")  # noqa: F821

    # Personas this account may write with. Empty list = every active persona.
    allowed_personas: Mapped[List["Persona"]] = relationship(  # noqa: F821
        secondary=user_personas, lazy="selectin"
    )
