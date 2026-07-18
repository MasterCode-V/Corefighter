"""Helpers for article versioning and loading generation context."""
from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Article,
    ArticleVersion,
    ContentRule,
    Persona,
    Purchase,
    Store,
)


async def next_version_no(db: AsyncSession, article_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.coalesce(func.max(ArticleVersion.version_no), 0)).where(
            ArticleVersion.article_id == article_id
        )
    )
    return int(result.scalar_one()) + 1


async def create_version(
    db: AsyncSession,
    article: Article,
    *,
    data: dict,
    generated_by_job_id: Optional[uuid.UUID] = None,
    regeneration_scope: Optional[str] = None,
    regeneration_instruction: Optional[str] = None,
    is_manual_edit: bool = False,
) -> ArticleVersion:
    """Create a new immutable version and set it as the article's current version.
    Previous versions are always preserved (workflow 8 requirement)."""
    version = ArticleVersion(
        article_id=article.id,
        version_no=await next_version_no(db, article.id),
        title=data.get("title", ""),
        introduction=data.get("introduction", ""),
        headings=data.get("headings", []) or [],
        body=data.get("body", ""),
        rendered_html=data.get("rendered_html", ""),
        excerpt=data.get("excerpt", ""),
        category_suggestion=data.get("category_suggestion"),
        tag_suggestions=data.get("tag_suggestions", []) or [],
        generated_by_job_id=generated_by_job_id,
        regeneration_scope=regeneration_scope,
        regeneration_instruction=regeneration_instruction,
        is_manual_edit=is_manual_edit,
    )
    db.add(version)
    await db.flush()
    article.current_version_id = version.id
    await db.flush()
    return version


async def load_generation_context(
    db: AsyncSession, purchase: Purchase
) -> tuple[Store, Optional[Persona], List[ContentRule]]:
    store = await db.get(Store, purchase.store_id)
    persona = await db.get(Persona, purchase.persona_id) if purchase.persona_id else None
    rules_result = await db.execute(
        select(ContentRule).where(
            ContentRule.is_active.is_(True),
            or_(ContentRule.store_id.is_(None), ContentRule.store_id == purchase.store_id),
        )
    )
    rules = list(rules_result.scalars().all())
    return store, persona, rules
