from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PurchaseMethodBase(BaseModel):
    label: str = Field(..., min_length=1, max_length=64)
    sort_order: int = 0
    is_active: bool = True
    requires_area: bool = False
    linked_store_id: Optional[uuid.UUID] = None


class PurchaseMethodCreate(PurchaseMethodBase):
    pass


class PurchaseMethodUpdate(BaseModel):
    label: Optional[str] = Field(None, min_length=1, max_length=64)
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    requires_area: Optional[bool] = None
    linked_store_id: Optional[uuid.UUID] = None


class PurchaseMethodRead(PurchaseMethodBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
