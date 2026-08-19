from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DBSession, require_admin
from app.enums import UserRole
from app.models import PurchaseMethod, Store
from app.schemas.purchase_method import (
    PurchaseMethodCreate,
    PurchaseMethodRead,
    PurchaseMethodUpdate,
)

router = APIRouter()


@router.get("", response_model=list[PurchaseMethodRead])
async def list_purchase_methods(db: DBSession, current_user: CurrentUser) -> list[PurchaseMethod]:
    stmt = select(PurchaseMethod).order_by(PurchaseMethod.sort_order, PurchaseMethod.label)
    if current_user.role != UserRole.ADMIN:
        stmt = stmt.where(PurchaseMethod.is_active.is_(True))
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post(
    "",
    response_model=PurchaseMethodRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_purchase_method(db: DBSession, body: PurchaseMethodCreate) -> PurchaseMethod:
    if body.linked_store_id:
        store = await db.get(Store, body.linked_store_id)
        if not store:
            raise HTTPException(status_code=404, detail="店舗が見つかりません")
    method = PurchaseMethod(**body.model_dump())
    db.add(method)
    await db.commit()
    await db.refresh(method)
    return method


@router.patch(
    "/{method_id}",
    response_model=PurchaseMethodRead,
    dependencies=[Depends(require_admin)],
)
async def update_purchase_method(
    db: DBSession, method_id: uuid.UUID, body: PurchaseMethodUpdate
) -> PurchaseMethod:
    method = await db.get(PurchaseMethod, method_id)
    if not method:
        raise HTTPException(status_code=404, detail="買取方法が見つかりません")
    data = body.model_dump(exclude_unset=True)
    if data.get("linked_store_id"):
        store = await db.get(Store, data["linked_store_id"])
        if not store:
            raise HTTPException(status_code=404, detail="店舗が見つかりません")
    for key, value in data.items():
        setattr(method, key, value)
    await db.commit()
    await db.refresh(method)
    return method


@router.delete(
    "/{method_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    dependencies=[Depends(require_admin)],
)
async def delete_purchase_method(db: DBSession, method_id: uuid.UUID) -> None:
    method = await db.get(PurchaseMethod, method_id)
    if not method:
        raise HTTPException(status_code=404, detail="買取方法が見つかりません")
    await db.delete(method)
    await db.commit()
