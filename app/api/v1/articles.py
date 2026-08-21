from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta
from typing import Annotated, List, Optional

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete as sa_delete, func, or_, select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.deps import CurrentUser, DBSession, ensure_store_access, get_arq
from app.enums import ArticleStatus, ImageType, JobType, RegenerationScope, UserRole
from app.models import (
    Article,
    ArticleVersion,
    Purchase,
    PurchaseProduct,
    SimilarityResult,
    Store,
)
from app.schemas.article import (
    ArticleEditRequest,
    ArticleListItem,
    ArticleListPage,
    ArticleRead,
    ArticleVersionRead,
    RegenerateRequest,
    RelatedPostItem,
    RelatedPostsUpdate,
    StoreArticleStats,
)
from app.schemas.job import JobCreatedResponse
from app.schemas.similarity import SimilarityResultRead
from app.services import article_service, article_template, job_service

router = APIRouter()
ArqDep = Annotated[ArqRedis, Depends(get_arq)]

def _status_filter(stmt, status_filter: Optional[ArticleStatus]):
    """Articles are operated in two states: 公開 (PUBLISHED) and 下書き (everything else).

    Legacy rows may still carry an approval-workflow status, so anything that is
    not PUBLISHED is treated as 下書き.
    """
    if status_filter is None:
        return stmt
    if status_filter == ArticleStatus.PUBLISHED:
        return stmt.where(Article.status == ArticleStatus.PUBLISHED)
    return stmt.where(Article.status != ArticleStatus.PUBLISHED)


async def _get_article(db, article_id: uuid.UUID) -> Article:
    result = await db.execute(
        select(Article)
        .options(selectinload(Article.current_version))
        .where(Article.id == article_id)
    )
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="記事が見つかりません")
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
    stmt = _status_filter(stmt, status_filter)
    if search:
        stmt = stmt.join(ArticleVersion, Article.current_version_id == ArticleVersion.id).where(
            ArticleVersion.title.ilike(f"%{search}%")
        )
    stmt = stmt.order_by(Article.updated_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _media_url(storage_key: str) -> str:
    return f"{settings.API_V1_PREFIX}/media/{storage_key}"


def _parse_day(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


ORDER_COLUMNS = {
    "updated_desc": Article.updated_at.desc(),
    "updated_asc": Article.updated_at.asc(),
    "created_desc": Article.created_at.desc(),
    "created_asc": Article.created_at.asc(),
}


@router.get("/browse", response_model=ArticleListPage)
async def browse_articles(
    db: DBSession,
    current_user: CurrentUser,
    status_filter: Optional[ArticleStatus] = Query(None, alias="status"),
    store_id: Optional[uuid.UUID] = None,
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    order: str = "updated_desc",
    limit: int = 30,
    offset: int = 0,
) -> ArticleListPage:
    """Paged article list for the card grid: filters, total count and card data."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    stmt = select(Article).join(Purchase, Article.purchase_id == Purchase.id)
    stmt = _scope_filter(stmt, current_user)
    if store_id and current_user.role == UserRole.ADMIN:
        stmt = stmt.where(Article.store_id == store_id)
    stmt = _status_filter(stmt, status_filter)
    if search:
        like = f"%{search.strip()}%"
        title_match = (
            select(ArticleVersion.id)
            .where(
                ArticleVersion.id == Article.current_version_id,
                ArticleVersion.title.ilike(like),
            )
            .exists()
        )
        product_match = (
            select(PurchaseProduct.id)
            .where(
                PurchaseProduct.purchase_id == Purchase.id,
                or_(
                    PurchaseProduct.manufacturer.ilike(like),
                    PurchaseProduct.product_name.ilike(like),
                    PurchaseProduct.model_number.ilike(like),
                ),
            )
            .exists()
        )
        stmt = stmt.where(
            or_(
                title_match,
                product_match,
                Purchase.manufacturer.ilike(like),
                Purchase.product_name.ilike(like),
                Purchase.model_number.ilike(like),
            )
        )
    start = _parse_day(date_from)
    if start:
        stmt = stmt.where(Article.created_at >= start)
    end = _parse_day(date_to)
    if end:
        stmt = stmt.where(Article.created_at < end + timedelta(days=1))

    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    page_stmt = (
        stmt.options(selectinload(Article.current_version))
        .order_by(ORDER_COLUMNS.get(order, ORDER_COLUMNS["updated_desc"]))
        .limit(limit)
        .offset(offset)
    )
    articles = list((await db.execute(page_stmt)).scalars().all())
    if not articles:
        return ArticleListPage(total=total, limit=limit, offset=offset, items=[])

    purchases_res = await db.execute(
        select(Purchase)
        .options(selectinload(Purchase.images), selectinload(Purchase.products))
        .where(Purchase.id.in_([a.purchase_id for a in articles]))
    )
    purchases = {p.id: p for p in purchases_res.scalars().all()}

    stores_res = await db.execute(
        select(Store).where(Store.id.in_({a.store_id for a in articles}))
    )
    store_names = {s.id: s.name for s in stores_res.scalars().all()}

    items: list[ArticleListItem] = []
    for article in articles:
        purchase = purchases.get(article.purchase_id)
        thumbnail = None
        manufacturer = product_name = model_number = ""
        product_count = 0
        if purchase:
            if purchase.images:
                ordered = sorted(
                    purchase.images,
                    key=lambda i: (i.image_type != ImageType.ARTICLE, i.sort_order),
                )
                thumbnail = _media_url(ordered[0].storage_key)
            if purchase.products:
                first = purchase.products[0]
                manufacturer = first.manufacturer or ""
                product_name = first.product_name or ""
                model_number = first.model_number or ""
                product_count = len(purchase.products)
            else:
                manufacturer = purchase.manufacturer or ""
                product_name = purchase.product_name or ""
                model_number = purchase.model_number or ""
                product_count = 1 if (manufacturer or product_name or model_number) else 0
        items.append(
            ArticleListItem(
                id=article.id,
                purchase_id=article.purchase_id,
                store_id=article.store_id,
                store_name=store_names.get(article.store_id, ""),
                status=article.status,
                title=article.current_version.title if article.current_version else "",
                thumbnail_url=thumbnail,
                manufacturer=manufacturer,
                product_name=product_name,
                model_number=model_number,
                product_count=product_count,
                published_url=article.published_url,
                wordpress_post_id=article.wordpress_post_id,
                created_at=article.created_at,
                updated_at=article.updated_at,
            )
        )
    return ArticleListPage(total=total, limit=limit, offset=offset, items=items)


@router.get("/stats", response_model=list[StoreArticleStats])
async def article_stats(db: DBSession, current_user: CurrentUser) -> list[StoreArticleStats]:
    """Per-store published / draft counters shown as chips above the list."""
    counts_stmt = select(Article.store_id, Article.status, func.count()).group_by(
        Article.store_id, Article.status
    )
    counts_stmt = _scope_filter(counts_stmt, current_user)
    rows = (await db.execute(counts_stmt)).all()

    stores_stmt = select(Store).order_by(Store.sort_order, Store.name)
    if current_user.role != UserRole.ADMIN and current_user.store_id:
        stores_stmt = stores_stmt.where(Store.id == current_user.store_id)
    stores = list((await db.execute(stores_stmt)).scalars().all())

    published: dict[uuid.UUID, int] = {}
    totals: dict[uuid.UUID, int] = {}
    for store_key, article_status, count in rows:
        totals[store_key] = totals.get(store_key, 0) + count
        if article_status == ArticleStatus.PUBLISHED:
            published[store_key] = published.get(store_key, 0) + count

    return [
        StoreArticleStats(
            store_id=store.id,
            store_name=store.name,
            published=published.get(store.id, 0),
            draft=totals.get(store.id, 0) - published.get(store.id, 0),
            total=totals.get(store.id, 0),
        )
        for store in stores
    ]


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
        raise HTTPException(status_code=400, detail="編集できる記事バージョンがありません")

    merged = {
        "title": body.title if body.title is not None else current.title,
        "introduction": body.introduction if body.introduction is not None else current.introduction,
        "headings": body.headings if body.headings is not None else current.headings,
        "body": body.body if body.body is not None else current.body,
        "rendered_html": body.rendered_html if body.rendered_html is not None else current.rendered_html,
        "excerpt": body.excerpt if body.excerpt is not None else current.excerpt,
        "category_suggestion": body.category_suggestion
        if body.category_suggestion is not None else current.category_suggestion,
        "tag_suggestions": article_template.filter_content_tags(
            body.tag_suggestions if body.tag_suggestions is not None else current.tag_suggestions,
        ),
    }

    # Rebuild assembled HTML so heading / thanks / footer (phones, LINE)
    # always match the latest store template, unless the caller sent full HTML.
    if body.rendered_html is None:
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
        product_line = None
        if purchase:
            if purchase.images:
                images = sorted(
                    purchase.images,
                    key=lambda i: (i.image_type != ImageType.ARTICLE, i.sort_order),
                )
                main_url = images[0].url
            product_line = article_template.build_product_line(cfg, purchase)
        merged["rendered_html"] = article_template.assemble_html(
            cfg,
            heading,
            merged["body"],
            main_image_url=main_url,
            product_line=product_line,
            related_posts=article.related_posts or [],
        )

    await article_service.create_version(db, article, data=merged, is_manual_edit=True)

    if article.wordpress_post_id:
        await job_service.create_job(
            db, arq, job_type=JobType.WORDPRESS_UPDATE,
            article_id=article.id, created_by=current_user.id,
        )
    await db.commit()
    return await _get_article(db, article_id)


@router.get("/{article_id}/related-candidates", response_model=list[RelatedPostItem])
async def related_candidates(
    db: DBSession,
    current_user: CurrentUser,
    article_id: uuid.UUID,
    q: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
) -> list[RelatedPostItem]:
    """Search published articles that can be picked as related posts."""
    article = await _get_article(db, article_id)
    ensure_store_access(current_user, article.store_id)

    stmt = (
        select(Article)
        .options(selectinload(Article.current_version))
        .where(
            Article.id != article_id,
            Article.status == ArticleStatus.PUBLISHED,
        )
        .order_by(Article.updated_at.desc())
        .limit(limit * 3)
    )
    stmt = _scope_filter(stmt, current_user)
    rows = list((await db.execute(stmt)).scalars().all())

    needle = (q or "").strip().lower()
    out: list[RelatedPostItem] = []
    for row in rows:
        title = (row.current_version.title if row.current_version else "") or ""
        plain = re.sub(r"<[^>]+>", "", title).replace("&nbsp;", " ").strip()
        if needle and needle not in plain.lower() and needle not in (row.published_url or "").lower():
            continue
        date = ""
        if row.published_at:
            date = row.published_at.isoformat()
        elif row.updated_at:
            date = row.updated_at.isoformat()
        out.append(
            RelatedPostItem(
                id=row.wordpress_post_id,
                article_id=row.id,
                title=plain or title,
                link=row.published_url or "",
                date=date,
                thumbnail=None,
                score=None,
            )
        )
        if len(out) >= limit:
            break
    return out


@router.put("/{article_id}/related", response_model=ArticleRead)
async def update_related_posts(
    db: DBSession,
    current_user: CurrentUser,
    arq: ArqDep,
    article_id: uuid.UUID,
    body: RelatedPostsUpdate,
) -> Article:
    """Save up to 4 manually selected related articles and refresh rendered HTML."""
    article = await _get_article(db, article_id)
    ensure_store_access(current_user, article.store_id)

    items = []
    for row in (body.items or [])[:4]:
        title = (row.title or "").strip()
        if not title:
            continue
        items.append(
            {
                "id": row.id,
                "article_id": str(row.article_id) if row.article_id else None,
                "title": title,
                "link": (row.link or "").strip(),
                "date": row.date or "",
                "thumbnail": row.thumbnail,
                "score": row.score,
            }
        )
    article.related_posts = items

    current = article.current_version
    if current:
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
        product_line = None
        if purchase:
            if purchase.images:
                images = sorted(
                    purchase.images,
                    key=lambda i: (i.image_type != ImageType.ARTICLE, i.sort_order),
                )
                main_url = images[0].url
            product_line = article_template.build_product_line(cfg, purchase)
        rendered = article_template.assemble_html(
            cfg,
            heading,
            current.body,
            main_image_url=main_url,
            product_line=product_line,
            related_posts=items,
        )
        await article_service.create_version(
            db,
            article,
            data={
                "title": current.title,
                "introduction": current.introduction,
                "headings": current.headings,
                "body": current.body,
                "rendered_html": rendered,
                "excerpt": current.excerpt,
                "category_suggestion": current.category_suggestion,
                "tag_suggestions": current.tag_suggestions,
            },
            is_manual_edit=True,
        )
        if article.wordpress_post_id:
            await job_service.create_job(
                db,
                arq,
                job_type=JobType.WORDPRESS_UPDATE,
                article_id=article.id,
                created_by=current_user.id,
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


@router.delete("/{article_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_article(
    db: DBSession, current_user: CurrentUser, article_id: uuid.UUID
) -> None:
    """Remove an article together with its purchase, versions and images.

    The WordPress post (if any) is intentionally left untouched — deleting here
    only clears the record from CORE FIGHTER.
    """
    article = await _get_article(db, article_id)
    ensure_store_access(current_user, article.store_id)
    purchase_id = article.purchase_id

    res = await db.execute(
        select(Purchase).options(selectinload(Purchase.images)).where(Purchase.id == purchase_id)
    )
    purchase = res.scalar_one_or_none()
    if purchase:
        from app.core.storage import storage

        for image in purchase.images:
            try:
                await storage.delete(image.storage_key)
            except Exception:  # noqa: BLE001 - best effort cleanup
                pass

    await db.execute(sa_delete(Article).where(Article.id == article_id))
    await db.execute(sa_delete(Purchase).where(Purchase.id == purchase_id))
    await db.commit()
