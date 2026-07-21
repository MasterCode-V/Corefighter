from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.enums import UserRole


class UserBase(BaseModel):
    # Plain str: EmailStr rejects .local (dev) domains as reserved special-use names.
    email: str = Field(min_length=3, max_length=255)
    full_name: str = ""
    role: UserRole = UserRole.STORE_STAFF
    store_id: Optional[uuid.UUID] = None


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    store_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    created_at: datetime
