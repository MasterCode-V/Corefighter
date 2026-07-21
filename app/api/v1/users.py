from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DBSession, require_admin
from app.core.security import hash_password
from app.models import User
from app.schemas.user import UserCreate, UserRead, UserUpdate

router = APIRouter()


@router.get("", response_model=list[UserRead], dependencies=[Depends(require_admin)])
async def list_users(db: DBSession) -> list[User]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_admin)])
async def create_user(db: DBSession, body: UserCreate) -> User:
    exists = await db.execute(select(User).where(User.email == body.email))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        email=body.email,
        full_name=body.full_name,
        role=body.role,
        store_id=body.store_id,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserRead, dependencies=[Depends(require_admin)])
async def get_user(db: DBSession, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserRead, dependencies=[Depends(require_admin)])
async def update_user(db: DBSession, user_id: uuid.UUID, body: UserUpdate) -> User:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    data = body.model_dump(exclude_unset=True)
    if "password" in data and data["password"]:
        user.hashed_password = hash_password(data.pop("password"))
    else:
        data.pop("password", None)
    for key, value in data.items():
        setattr(user, key, value)
    await db.commit()
    await db.refresh(user)
    return user
