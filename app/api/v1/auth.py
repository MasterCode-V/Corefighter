from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.core.deps import CurrentUser, DBSession
from app.core.security import (
    ACCESS_TOKEN,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models import User
from app.schemas.auth import RefreshRequest, Token
from app.schemas.user import UserRead

router = APIRouter()


async def _authenticate(db, email: str, password: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return user


def _tokens(user: User) -> Token:
    extra = {"role": user.role.value, "store_id": str(user.store_id) if user.store_id else None}
    return Token(
        access_token=create_access_token(str(user.id), extra),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/login", response_model=Token)
async def login(db: DBSession, form: OAuth2PasswordRequestForm = Depends()) -> Token:
    """OAuth2 password flow. `username` field carries the email."""
    user = await _authenticate(db, form.username, form.password)
    return _tokens(user)


@router.post("/refresh", response_model=Token)
async def refresh(db: DBSession, body: RefreshRequest) -> Token:
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    user = await db.get(User, uuid.UUID(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    return _tokens(user)


@router.get("/me", response_model=UserRead)
async def me(current_user: CurrentUser) -> User:
    return current_user
