from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select

from app.core.deps import CurrentUser, DBSession, require_manager
from app.enums import ContentRuleType, UserRole
from app.models import ContentRule
from app.schemas.content_rule import ContentRuleCreate, ContentRuleRead, ContentRuleUpdate

router = APIRouter()


@router.get("", response_model=list[ContentRuleRead])
async def list_rules(
    db: DBSession,
    current_user: CurrentUser,
    store_id: Optional[uuid.UUID] = None,
    rule_type: Optional[ContentRuleType] = None,
) -> list[ContentRule]:
    stmt = select(ContentRule)
    if rule_type:
        stmt = stmt.where(ContentRule.rule_type == rule_type)
    if store_id:
        stmt = stmt.where(or_(ContentRule.store_id.is_(None), ContentRule.store_id == store_id))
    elif current_user.role != UserRole.ADMIN and current_user.store_id:
        stmt = stmt.where(
            or_(ContentRule.store_id.is_(None), ContentRule.store_id == current_user.store_id)
        )
    result = await db.execute(stmt.order_by(ContentRule.rule_type))
    return list(result.scalars().all())


@router.post("", response_model=ContentRuleRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_manager)])
async def create_rule(db: DBSession, body: ContentRuleCreate) -> ContentRule:
    rule = ContentRule(**body.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.patch("/{rule_id}", response_model=ContentRuleRead,
              dependencies=[Depends(require_manager)])
async def update_rule(db: DBSession, rule_id: uuid.UUID, body: ContentRuleUpdate) -> ContentRule:
    rule = await db.get(ContentRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(rule, key, value)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT,
               response_model=None, dependencies=[Depends(require_manager)])
async def delete_rule(db: DBSession, rule_id: uuid.UUID):
    rule = await db.get(ContentRule, rule_id)
    if rule:
        await db.delete(rule)
        await db.commit()
