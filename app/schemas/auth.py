from __future__ import annotations

from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str
