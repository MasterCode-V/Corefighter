"""FastAPI dependencies: auth, current user and role guards."""
from __future__ import annotations

import uuid
from typing import Annotated, AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_arq_pool
from app.core.security import ACCESS_TOKEN, decode_token
from app.enums import UserRole
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")

DBSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DBSession,
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if not payload or payload.get("type") != ACCESS_TOKEN:
        raise credentials_exc
    subject = payload.get("sub")
    if not subject:
        raise credentials_exc
    try:
        user_id = uuid.UUID(subject)
    except (ValueError, TypeError):
        raise credentials_exc

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_exc
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole):
    async def _guard(current_user: CurrentUser) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this action",
            )
        return current_user

    return _guard


require_admin = require_roles(UserRole.ADMIN)
require_manager = require_roles(UserRole.ADMIN, UserRole.STORE_MANAGER)


def ensure_store_access(user: User, store_id: uuid.UUID) -> None:
    """Store-scoped users may only touch their own store; admins see everything."""
    if user.role == UserRole.ADMIN:
        return
    if user.store_id != store_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this store's resources",
        )


async def get_arq():
    return await get_arq_pool()
