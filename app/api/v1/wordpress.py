from __future__ import annotations

import uuid
from typing import Annotated, List, Optional

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from app.core.deps import CurrentUser, DBSession, ensure_store_access, get_arq, require_admin
from app.core.security import decrypt_secret
from app.enums import ArticleStatus, JobType
from app.integrations.wordpress_client import WordPressClient, WordPressError
from app.models import Article, SimilarityResult, WordPressSite
from app.schemas.job import JobCreatedResponse
from app.services import job_service

router = APIRouter()
ArqDep = Annotated[ArqRedis, Depends(get_arq)]


class RelatedPost(BaseModel):
    id: Optional[int] = None
    title: str = ""
    link: str = ""
    date: str = ""
    thumbnail: Optional[str] = None
    score: Optional[float] = None


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
    """Fetch YARPP related posts for a published article (workflow: related section).

    Mirrors the YARPP block shown on the live WordPress post
    (`年間買取10000件 パワトレ買取実績`). Requires the article to be published
    to WordPress and YARPP's REST API to be enabled.
    """
    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    ensure_store_access(current_user, article.store_id)
    if not article.wordpress_post_id:
        raise HTTPException(
            status_code=400,
            detail="Article is not published to WordPress yet (no related posts available)",
        )
    site = await _resolve_site(db, article)
    if not site:
        raise HTTPException(status_code=400, detail="No WordPress site configured for this store")

    client = WordPressClient(site.base_url, site.username, decrypt_secret(site.encrypted_app_password))
    try:
        raw = await client.get_related_posts(article.wordpress_post_id, limit=limit)
    except WordPressError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [RelatedPost(**item) for item in client.normalize_related(raw)]


@router.post("/{article_id}/publish", response_model=JobCreatedResponse,
             status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_admin)])
async def publish_article(
    db: DBSession, current_user: CurrentUser, arq: ArqDep, article_id: uuid.UUID
) -> JobCreatedResponse:
    """Workflow 13: verify preconditions then enqueue WORDPRESS_PUBLISH."""
    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Verify approval + existing WordPress draft + similarity result.
    if article.status not in (ArticleStatus.WORDPRESS_DRAFT, ArticleStatus.APPROVED):
        raise HTTPException(status_code=400, detail="Article must be approved and have a WordPress draft")
    if not article.wordpress_post_id:
        raise HTTPException(status_code=400, detail="No WordPress draft exists yet")
    if not article.current_version_id:
        raise HTTPException(status_code=400, detail="Article has no content")

    sim = await db.execute(
        select(SimilarityResult)
        .where(SimilarityResult.article_id == article_id)
        .order_by(SimilarityResult.created_at.desc())
        .limit(1)
    )
    latest = sim.scalar_one_or_none()
    if latest and not latest.passed:
        raise HTTPException(
            status_code=400,
            detail="Latest similarity check did not pass; regenerate or override required",
        )

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
        raise HTTPException(status_code=404, detail="Article not found")
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
            raise HTTPException(status_code=404, detail="WordPress site not found")
    job = await job_service.create_job(
        db, arq, job_type=JobType.WORDPRESS_SYNC, created_by=current_user.id,
        payload={"wordpress_site_id": str(wordpress_site_id) if wordpress_site_id else None},
    )
    await db.commit()
    return JobCreatedResponse(job_id=job.id, job_type=job.job_type, status=job.status)
