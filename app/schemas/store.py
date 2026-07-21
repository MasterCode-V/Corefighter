from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class StoreBase(BaseModel):
    name: str
    code: str
    address: str = ""
    description: str = ""
    article_config: dict = Field(default_factory=dict)


class StoreCreate(StoreBase):
    pass


class StoreUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    article_config: Optional[dict] = None


class StoreRead(StoreBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    created_at: datetime


# --------------------------------------------------------------------------
# WordPress site configuration
# --------------------------------------------------------------------------
class WordPressSiteBase(BaseModel):
    name: str = ""
    base_url: str
    username: str
    default_category_id: Optional[int] = None
    default_author_id: Optional[int] = None


class WordPressSiteCreate(WordPressSiteBase):
    app_password: str = Field(..., description="WordPress application password (stored encrypted)")


class WordPressSiteUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    username: Optional[str] = None
    app_password: Optional[str] = None
    default_category_id: Optional[int] = None
    default_author_id: Optional[int] = None
    is_active: Optional[bool] = None


class WordPressSiteRead(WordPressSiteBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_id: uuid.UUID
    is_active: bool
    created_at: datetime
