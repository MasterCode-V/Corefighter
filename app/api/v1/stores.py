from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from pydantic import BaseModel

from app.core.deps import CurrentUser, DBSession, ensure_store_access, require_admin, require_manager
from app.core.security import encrypt_secret
from app.enums import UserRole
from app.models import Store, WordPressSite
from app.schemas.store import (
    StoreCreate,
    StoreRead,
    StoreUpdate,
    WordPressSiteCreate,
    WordPressSiteRead,
    WordPressSiteUpdate,
)
from app.services import article_template

router = APIRouter()


# Keys that make up the editable article template (footer, phone, addresses...).
TEMPLATE_KEYS = {
    "label", "area", "title_prefix", "title_suffix",
    "heading_prefix", "heading_suffix", "thanks_text", "thanks_color",
    "persona_intro", "many_threshold", "phone_general", "phone_dispatch",
    "footer_html", "style",
}


class ArticleTemplateUpdate(BaseModel):
    """Partial update of a store's article template (only provided keys change)."""

    label: str | None = None
    area: str | None = None
    thanks_text: str | None = None
    thanks_color: str | None = None
    persona_intro: str | None = None
    phone_general: str | None = None
    phone_dispatch: str | None = None
    footer_html: str | None = None


@router.get("", response_model=list[StoreRead])
async def list_stores(db: DBSession, current_user: CurrentUser) -> list[Store]:
    stmt = select(Store).order_by(Store.name)
    if current_user.role != UserRole.ADMIN and current_user.store_id:
        stmt = stmt.where(Store.id == current_user.store_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=StoreRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_admin)])
async def create_store(db: DBSession, body: StoreCreate) -> Store:
    store = Store(**body.model_dump())
    db.add(store)
    await db.commit()
    await db.refresh(store)
    return store


@router.get("/{store_id}", response_model=StoreRead)
async def get_store(db: DBSession, store_id: uuid.UUID) -> Store:
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.patch("/{store_id}", response_model=StoreRead, dependencies=[Depends(require_admin)])
async def update_store(db: DBSession, store_id: uuid.UUID, body: StoreUpdate) -> Store:
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(store, key, value)
    await db.commit()
    await db.refresh(store)
    return store


@router.get("/{store_id}/article-template")
async def get_article_template(
    db: DBSession, current_user: CurrentUser, store_id: uuid.UUID
) -> dict:
    """Return the store's fully-resolved article template (defaults + overrides)."""
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    ensure_store_access(current_user, store_id)
    cfg = article_template.resolve_config(store)
    return {"resolved": cfg, "overrides": store.article_config or {}}


@router.patch("/{store_id}/article-template", response_model=StoreRead,
              dependencies=[Depends(require_manager)])
async def update_article_template(
    db: DBSession, current_user: CurrentUser, store_id: uuid.UUID, body: ArticleTemplateUpdate
) -> Store:
    """Edit the fixed template part of articles (footer, phone, address, etc.).

    Persisted per store so every future article for that store uses it. Store
    managers may edit their own store; admins may edit any store.
    """
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    ensure_store_access(current_user, store_id)
    overrides = dict(store.article_config or {})
    for key, value in body.model_dump(exclude_unset=True).items():
        if key in TEMPLATE_KEYS and value is not None:
            overrides[key] = value
    store.article_config = overrides
    await db.commit()
    await db.refresh(store)
    return store


# --------------------------------------------------------------------------
# WordPress site configuration (per store)
# --------------------------------------------------------------------------
@router.get("/{store_id}/wordpress", response_model=list[WordPressSiteRead])
async def list_wp_sites(db: DBSession, store_id: uuid.UUID) -> list[WordPressSite]:
    result = await db.execute(
        select(WordPressSite).where(WordPressSite.store_id == store_id)
    )
    return list(result.scalars().all())


@router.post("/{store_id}/wordpress", response_model=WordPressSiteRead,
             status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
async def create_wp_site(
    db: DBSession, store_id: uuid.UUID, body: WordPressSiteCreate
) -> WordPressSite:
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    data = body.model_dump()
    app_password = data.pop("app_password")
    site = WordPressSite(
        store_id=store_id,
        encrypted_app_password=encrypt_secret(app_password),
        **data,
    )
    db.add(site)
    await db.commit()
    await db.refresh(site)
    return site


@router.patch("/wordpress/{site_id}", response_model=WordPressSiteRead,
              dependencies=[Depends(require_admin)])
async def update_wp_site(
    db: DBSession, site_id: uuid.UUID, body: WordPressSiteUpdate
) -> WordPressSite:
    site = await db.get(WordPressSite, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="WordPress site not found")
    data = body.model_dump(exclude_unset=True)
    if data.get("app_password"):
        site.encrypted_app_password = encrypt_secret(data.pop("app_password"))
    else:
        data.pop("app_password", None)
    for key, value in data.items():
        setattr(site, key, value)
    await db.commit()
    await db.refresh(site)
    return site
