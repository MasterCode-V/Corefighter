from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PersonaBase(BaseModel):
    name: str
    description: str = ""
    tone: str = ""
    writing_style: str = ""
    system_prompt: str = ""
    store_id: Optional[uuid.UUID] = None


class PersonaCreate(PersonaBase):
    pass


class PersonaUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tone: Optional[str] = None
    writing_style: Optional[str] = None
    system_prompt: Optional[str] = None
    is_active: Optional[bool] = None


class PersonaRead(PersonaBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    created_at: datetime
