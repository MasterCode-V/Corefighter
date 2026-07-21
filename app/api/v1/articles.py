from __future__ import annotations

import uuid
from typing import Annotated, List, Optional

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DBSession, ensure_store_access, get_arq
from app.enums import ArticleStatus, ImageType, JobType, RegenerationScope, UserRole
from app.models import Article, ArticleVersion, Purchase, SimilarityResult, Store
from app.schemas.article import (
    ArticleEditRequest,
    ArticleRead,
    ArticleVersionRead,
    RegenerateRequest,
)
from app.schemas.job import JobCreatedResponse
from app.schemas.similarity import SimilarityResultRead
from app.services import article_service, article_template, job_service

router = APIRouter()
ArqDep = Annotated[ArqRedis, Depends(get_arq)]

WAITING_LIST_STATUSES = [
    ArticleStatus.WAITING_LIST,
    ArticleStatus.SIMILARITY_WARNING,
    ArticleStatus.NEEDS_CORRECTION,
]


async def _get_article(db, article_id: uuid.UUID) -> Article:
    result = await db.execute(
        select(Article)
        .options(selectinload(Article.current_version))
        .where(Article.id == article_id)
    )
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


def _scope_filter(stmt, current_user):
    if current_user.role != UserRole.ADMIN and current_user.store_id:
        stmt = stmt.where(Article.store_id == current_user.store_id)
    return stmt


@router.get("", response_model=list[ArticleRead])
async def list_articles(
    db: DBSession,
    current_user: CurrentUser,
    status_filter: Optional[ArticleStatus] = Query(None, alias="status"),
    store_id: Optional[uuid.UUID] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Article]:
    stmt = select(Article).options(selectinload(Article.current_version))
    stmt = _scope_filter(stmt, current_user)
    if store_id and current_user.role == UserRole.ADMIN:
        stmt = stmt.where(Article.store_id == store_id)
    if status_filter:
        stmt = stmt.where(Article.status == status_filter)
    if search:
        stmt = stmt.join(ArticleVersion, Article.current_version_id == ArticleVersion.id).where(
            ArticleVersion.title.ilike(f"%{search}%")
        )
    stmt = stmt.order_by(Article.updated_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/waiting-list", response_model=list[ArticleRead])
async def publication_waiting_list(
    db: DBSession, current_user: CurrentUser
) -> list[Article]:
    """Workflow 9: articles awaiting review before submission/approval."""
    stmt = select(Article).options(selectinload(Article.current_version)).where(
        Article.status.in_(WAITING_LIST_STATUSES)
    )
    stmt = _scope_filter(stmt, current_user)
    result = await db.execute(stmt.order_by(Article.updated_at.desc()))
    return list(result.scalars().all())


@router.get("/{article_id}", response_model=ArticleRead)
async def get_article(db: DBSession, current_user: CurrentUser, article_id: uuid.UUID) -> Article:
    article = await _get_article(db, article_id)
    ensure_store_access(current_user, article.store_id)
    return article


@router.get("/{article_id}/versions", response_model=list[ArticleVersionRead])
async def list_versions(
    db: DBSession, current_user: CurrentUser, article_id: uuid.UUID
) -> list[ArticleVersion]:
    article = await _get_article(db, article_id)
    ensure_store_access(current_user, article.store_id)
    result = await db.execute(
        select(ArticleVersion)
        .where(ArticleVersion.article_id == article_id)
        .order_by(ArticleVersion.version_no.desc())
    )
    return list(result.scalars().all())


@router.get("/{article_id}/similarity", response_model=list[SimilarityResultRead])
async def similarity_results(
    db: DBSession, current_user: CurrentUser, article_id: uuid.UUID
) -> list[SimilarityResult]:
    article = await _get_article(db, article_id)
    ensure_store_access(current_user, article.store_id)
    result = await db.execute(
        select(SimilarityResult)
        .where(SimilarityResult.article_id == article_id)
        .order_by(SimilarityResult.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/{article_id}/edit", response_model=ArticleRead)
async def edit_article(
    db: DBSession,
    current_user: CurrentUser,
    arq: ArqDep,
    article_id: uuid.UUID,
    body: ArticleEditRequest,
) -> Article:
    """Minor manual edit -> new version (workflow 9). If a WordPress draft
    already exists, enqueue a WORDPRESS_UPDATE job (workflow 12)."""
    article = await _get_article(db, article_id)
    ensure_store_access(current_user, article.store_id)
    current = article.current_version
    if not current:
        raise HTTPException(status_code=400, detail="Article has no version to edit")

    merged = {
        "title": body.title if body.title is not None else current.title,
        "introduction": body.introduction if body.introduction is not None else current.introduction,
        "headings": body.headings if body.headings is not None else current.headings,
        "body": body.body if body.body is not None else current.body,
        "rendered_html": body.rendered_html if body.rendered_html is not None else current.rendered_html,
        "excerpt": body.excerpt if body.excerpt is not None else current.excerpt,
        "category_suggestion": body.category_suggestion
        if body.category_suggestion is not None else current.category_suggestion,
        "tag_suggestions": body.tag_suggestions
        if body.tag_suggestions is not None else current.tag_suggestions,
    }

    # If the caller edited the body/title but did NOT supply full rendered HTML,
    # rebuild it from the template so the fixed heading/thanks/footer stay intact.
    if body.rendered_html is None and body.body is not None:
        store = await db.get(Store, article.store_id)
        cfg = article_template.resolve_config(store)
        heading = article_template.build_heading(cfg)
        pres = await db.execute(
            select(Purchase)
            .options(selectinload(Purchase.images), selectinload(Purchase.products))
            .where(Purchase.id == article.purchase_id)
        )
        purchase = pres.scalar_one_or_none()
        main_url = None
        if purchase and purchase.images:
            images = sorted(
                purchase.images,
                key=lambda i: (i.image_type != ImageType.ARTICLE, i.sort_order),
            )
            main_url = images[0].url
        merged["rendered_html"] = article_template.assemble_html(
            cfg, heading, merged["body"], main_image_url=main_url
        )

    await article_service.create_version(db, article, data=merged, is_manual_edit=True)

    if article.wordpress_post_id:
        await job_service.create_job(
            db, arq, job_type=JobType.WORDPRESS_UPDATE,
            article_id=article.id, created_by=current_user.id,
        )
    await db.commit()
    return await _get_article(db, article_id)


@router.post("/{article_id}/regenerate", response_model=JobCreatedResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def regenerate_article(
    db: DBSession,
    current_user: CurrentUser,
    arq: ArqDep,
    article_id: uuid.UUID,
    body: RegenerateRequest,
) -> JobCreatedResponse:
    """Workflow 8: regenerate all/part of the article. History is preserved."""
    article = await _get_article(db, article_id)
    ensure_store_access(current_user, article.store_id)
    job = await job_service.create_job(
        db, arq, job_type=JobType.REGENERATION,
        purchase_id=article.purchase_id, article_id=article.id, created_by=current_user.id,
        payload={
            "scope": body.scope.value,
            "instruction": body.instruction,
            "target_section": body.target_section,
        },
    )
    await db.commit()
    return JobCreatedResponse(job_id=job.id, job_type=job.job_type, status=job.status)


@router.post("/{article_id}/similarity-check", response_model=JobCreatedResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def trigger_similarity(
    db: DBSession, current_user: CurrentUser, arq: ArqDep, article_id: uuid.UUID
) -> JobCreatedResponse:
    """Workflow 7: manually (re)run the similarity check."""
    article = await _get_article(db, article_id)
    ensure_store_access(current_user, article.store_id)
    job = await job_service.create_job(
        db, arq, job_type=JobType.SIMILARITY_CHECK,
        article_id=article.id, created_by=current_user.id,
    )
    await db.commit()
    return JobCreatedResponse(job_id=job.id, job_type=job.job_type, status=job.status)
