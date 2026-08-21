from __future__ import annotations

import uuid
from typing import Annotated, List, Optional

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DBSession, ensure_store_access, get_arq, require_admin
from app.core.security import decrypt_secret
from app.enums import ArticleStatus, JobType, UserRole
from app.integrations.wordpress_client import WordPressClient, WordPressError
from app.models import Article, WordPressSite
from app.schemas.job import JobCreatedResponse
from app.services import job_service
from app.services.wordpress_categories import (
    PRODUCT_CATEGORY_NAMES,
    WORDPRESS_CATEGORIES,
)

router = APIRouter()
ArqDep = Annotated[ArqRedis, Depends(get_arq)]


class RelatedPost(BaseModel):
    id: Optional[int] = None
    article_id: Optional[uuid.UUID] = None
    title: str = ""
    link: str = ""
    date: str = ""
    thumbnail: Optional[str] = None
    score: Optional[float] = None


class WordpressCategory(BaseModel):
    id: int
    name: str
    is_product: bool = True


class WordpressTag(BaseModel):
    id: int
    name: str
    count: int = 0


@router.get("/categories", response_model=List[WordpressCategory])
async def list_wordpress_categories(
    current_user: CurrentUser,
    product_only: bool = Query(True),
) -> List[WordpressCategory]:
    """Return the buyersbox WordPress category catalog used for article posting."""
    rows: List[WordpressCategory] = []
    product_set = set(PRODUCT_CATEGORY_NAMES)
    for row in WORDPRESS_CATEGORIES:
        is_product = row["name"] in product_set
        if product_only and not is_product:
            continue
        rows.append(WordpressCategory(id=row["id"], name=row["name"], is_product=is_product))
    return rows


@router.get("/tags", response_model=List[WordpressTag])
async def list_wordpress_tags(
    db: DBSession,
    current_user: CurrentUser,
    search: Optional[str] = Query(None),
    store_id: Optional[uuid.UUID] = None,
    limit: int = Query(100, ge=1, le=200),
) -> List[WordpressTag]:
    """List existing WordPress tags so staff can pick from the live catalog."""
    stmt = select(WordPressSite).where(WordPressSite.is_active.is_(True))
    if store_id:
        ensure_store_access(current_user, store_id)
        stmt = stmt.where(WordPressSite.store_id == store_id)
    elif current_user.role != UserRole.ADMIN and current_user.store_id:
        stmt = stmt.where(WordPressSite.store_id == current_user.store_id)
    site = (await db.execute(stmt.limit(1))).scalar_one_or_none()
    if not site:
        return []

    client = WordPressClient(
        site.base_url, site.username, decrypt_secret(site.encrypted_app_password)
    )
    try:
        raw = await client.list_tags(search=search, limit=limit)
    except WordPressError:
        return []
    return [
        WordpressTag(id=int(t["id"]), name=str(t.get("name") or ""), count=int(t.get("count") or 0))
        for t in raw
        if t.get("id") and t.get("name")
    ]


async def _resolve_site(db, article: Article) -> Optional[WordPressSite]:
    if article.wordpress_site_id:
        site = await db.get(WordPressSite, article.wordpress_site_id)
        if site:
            return site
    result = await db.execute(
        select(WordPressSite).where(
            WordPressSite.store_id == article.store_id,
            WordPressSite.is_active.is_(True),
        ).limit(1)
    )
    return result.scalar_one_or_none()


@router.get("/{article_id}/related", response_model=List[RelatedPost])
async def related_posts(
    db: DBSession,
    current_user: CurrentUser,
    article_id: uuid.UUID,
    limit: int = Query(4, ge=1, le=20),
) -> List[RelatedPost]:
    """Return up to ``limit`` related articles (default 4).

    Prefer manually saved selections when present. Otherwise use WordPress YARPP
    (when a WP post id exists) and fall back to recent published CORE FIGHTER
    articles so the editor can still preview four cards.
    """
    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="記事が見つかりません")
    ensure_store_access(current_user, article.store_id)

    manual = list(article.related_posts or [])
    if manual:
        items: List[RelatedPost] = []
        for row in manual[:limit]:
            aid = row.get("article_id")
            try:
                article_uuid = uuid.UUID(str(aid)) if aid else None
            except (TypeError, ValueError):
                article_uuid = None
            items.append(
                RelatedPost(
                    id=row.get("id"),
                    article_id=article_uuid,
                    title=row.get("title") or "",
                    link=row.get("link") or "",
                    date=row.get("date") or "",
                    thumbnail=row.get("thumbnail"),
                    score=row.get("score"),
                )
            )
        return items

    items = []
    if article.wordpress_post_id:
        site = await _resolve_site(db, article)
        if site:
            client = WordPressClient(
                site.base_url, site.username, decrypt_secret(site.encrypted_app_password)
            )
            try:
                raw = await client.get_related_posts(article.wordpress_post_id, limit=limit)
                items = [RelatedPost(**row) for row in client.normalize_related(raw)]
            except WordPressError:
                items = []

    if len(items) < limit:
        items.extend(await _local_related(db, article, limit - len(items), items))
    return items[:limit]


async def _local_related(
    db,
    article: Article,
    limit: int,
    already: List[RelatedPost],
) -> List[RelatedPost]:
    if limit <= 0:
        return []
    taken_links = {r.link for r in already if r.link}
    taken_ids = {r.id for r in already if r.id}
    stmt = (
        select(Article)
        .options(selectinload(Article.current_version))
        .where(
            Article.id != article.id,
            Article.status == ArticleStatus.PUBLISHED,
        )
        .order_by(Article.updated_at.desc())
        .limit(limit + 8)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    same = [a for a in rows if a.store_id == article.store_id]
    others = [a for a in rows if a.store_id != article.store_id]
    out: List[RelatedPost] = []
    for a in same + others:
        title = (a.current_version.title if a.current_version else "") or ""
        link = a.published_url or ""
        if not title:
            continue
        if link and link in taken_links:
            continue
        if a.wordpress_post_id and a.wordpress_post_id in taken_ids:
            continue
        date = ""
        if a.published_at:
            date = a.published_at.isoformat()
        elif a.updated_at:
            date = a.updated_at.isoformat()
        out.append(
            RelatedPost(
                id=a.wordpress_post_id,
                article_id=a.id,
                title=title,
                link=link,
                date=date,
                thumbnail=None,
                score=None,
            )
        )
        if len(out) >= limit:
            break
    return out


@router.post("/{article_id}/draft", response_model=JobCreatedResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def create_wordpress_draft(
    db: DBSession, current_user: CurrentUser, arq: ArqDep, article_id: uuid.UUID
) -> JobCreatedResponse:
    """Save the article to WordPress as a draft (下書き)."""
    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="記事が見つかりません")
    ensure_store_access(current_user, article.store_id)
    if article.status == ArticleStatus.PUBLISHED:
        raise HTTPException(
            status_code=400,
            detail="この記事は既に公開済みです。下書きに戻す場合はWordPress側で操作してください",
        )
    if not article.current_version_id:
        raise HTTPException(status_code=400, detail="記事本文がありません")
    site = await _resolve_site(db, article)
    if not site:
        raise HTTPException(status_code=400, detail="この店舗にWordPress接続が設定されていません")

    job = await job_service.create_job(
        db, arq, job_type=JobType.WORDPRESS_DRAFT,
        article_id=article.id, created_by=current_user.id,
    )
    await db.commit()
    return JobCreatedResponse(job_id=job.id, job_type=job.job_type, status=job.status)


@router.post("/{article_id}/publish", response_model=JobCreatedResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def publish_article(
    db: DBSession, current_user: CurrentUser, arq: ArqDep, article_id: uuid.UUID
) -> JobCreatedResponse:
    """Publish the article to WordPress (公開).

    The worker creates the post when no WordPress draft exists yet, so staff can
    publish straight from the generation wizard. A failed similarity check only
    produces a warning in the UI and never blocks publishing.
    """
    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="記事が見つかりません")
    ensure_store_access(current_user, article.store_id)
    if not article.current_version_id:
        raise HTTPException(status_code=400, detail="記事本文がありません")
    site = await _resolve_site(db, article)
    if not site:
        raise HTTPException(status_code=400, detail="この店舗にWordPress接続が設定されていません")

    job = await job_service.create_job(
        db, arq, job_type=JobType.WORDPRESS_PUBLISH,
        article_id=article.id, created_by=current_user.id,
    )
    await db.commit()
    return JobCreatedResponse(job_id=job.id, job_type=job.job_type, status=job.status)


@router.post("/{article_id}/retry", response_model=JobCreatedResponse,
             status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_admin)])
async def manual_retry(
    db: DBSession,
    current_user: CurrentUser,
    arq: ArqDep,
    article_id: uuid.UUID,
    job_type: JobType = JobType.WORDPRESS_PUBLISH,
) -> JobCreatedResponse:
    """Workflow 14: administrator manual retry after a WordPress failure."""
    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="記事が見つかりません")
    job = await job_service.create_job(
        db, arq, job_type=job_type, article_id=article.id, created_by=current_user.id,
    )
    await db.commit()
    return JobCreatedResponse(job_id=job.id, job_type=job.job_type, status=job.status)


@router.post("/sync", response_model=JobCreatedResponse, status_code=status.HTTP_202_ACCEPTED,
             dependencies=[Depends(require_admin)])
async def sync_corpus(
    db: DBSession,
    current_user: CurrentUser,
    arq: ArqDep,
    wordpress_site_id: Optional[uuid.UUID] = None,
) -> JobCreatedResponse:
    """Workflow 15: synchronize published WordPress articles into the corpus."""
    if wordpress_site_id:
        site = await db.get(WordPressSite, wordpress_site_id)
        if not site:
            raise HTTPException(status_code=404, detail="WordPress接続設定が見つかりません")
    job = await job_service.create_job(
        db, arq, job_type=JobType.WORDPRESS_SYNC, created_by=current_user.id,
        payload={"wordpress_site_id": str(wordpress_site_id) if wordpress_site_id else None},
    )
    await db.commit()
    return JobCreatedResponse(job_id=job.id, job_type=job.job_type, status=job.status)
