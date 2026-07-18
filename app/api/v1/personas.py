from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select

from app.core.deps import CurrentUser, DBSession, require_manager
from app.enums import UserRole
from app.models import Persona
from app.schemas.persona import PersonaCreate, PersonaRead, PersonaUpdate

router = APIRouter()


@router.get("", response_model=list[PersonaRead])
async def list_personas(db: DBSession, current_user: CurrentUser) -> list[Persona]:
    stmt = select(Persona).where(Persona.is_active.is_(True))
    if current_user.role != UserRole.ADMIN and current_user.store_id:
        # Global personas + the user's own store personas.
        stmt = stmt.where(
            or_(Persona.store_id.is_(None), Persona.store_id == current_user.store_id)
        )
    result = await db.execute(stmt.order_by(Persona.name))
    return list(result.scalars().all())


@router.post("", response_model=PersonaRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_manager)])
async def create_persona(db: DBSession, body: PersonaCreate) -> Persona:
    persona = Persona(**body.model_dump())
    db.add(persona)
    await db.commit()
    await db.refresh(persona)
    return persona


@router.get("/{persona_id}", response_model=PersonaRead)
async def get_persona(db: DBSession, persona_id: uuid.UUID) -> Persona:
    persona = await db.get(Persona, persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    return persona


@router.patch("/{persona_id}", response_model=PersonaRead,
              dependencies=[Depends(require_manager)])
async def update_persona(db: DBSession, persona_id: uuid.UUID, body: PersonaUpdate) -> Persona:
    persona = await db.get(Persona, persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(persona, key, value)
    await db.commit()
    await db.refresh(persona)
    return persona
