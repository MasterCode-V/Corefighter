from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.enums import ContentRuleType


class ContentRuleBase(BaseModel):
    rule_type: ContentRuleType
    value: str
    note: str = ""
    store_id: Optional[uuid.UUID] = None


class ContentRuleCreate(ContentRuleBase):
    pass


class ContentRuleUpdate(BaseModel):
    value: Optional[str] = None
    note: Optional[str] = None
    is_active: Optional[bool] = None


class ContentRuleRead(ContentRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    created_at: datetime
