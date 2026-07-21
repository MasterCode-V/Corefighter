from __future__ import annotations

import uuid
from typing import Annotated

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DBSession, ensure_store_access, get_arq, require_admin
from app.enums import ArticleStatus, JobType, UserRole
from app.models import Article
from app.schemas.article import ApprovalDecisionRequest, ArticleRead, SubmitForApprovalRequest
from app.services import job_service

router = APIRouter()
ArqDep = Annotated[ArqRedis, Depends(get_arq)]

SUBMITTABLE = {
    ArticleStatus.WAITING_LIST,
    ArticleStatus.SIMILARITY_WARNING,
    ArticleStatus.RETURNED,
    ArticleStatus.ON_HOLD,
    ArticleStatus.DRAFT,
}


async def _get_article(db, article_id: uuid.UUID) -> Article:
    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.post("/{article_id}/submit", response_model=ArticleRead)
async def submit_for_approval(
    db: DBSession, current_user: CurrentUser, article_id: uuid.UUID, body: SubmitForApprovalRequest
) -> Article:
    """Workflow 10: store staff submits an article for administrator approval."""
    article = await _get_article(db, article_id)
    ensure_store_access(current_user, article.store_id)
    if article.status not in SUBMITTABLE:
        raise HTTPException(
            status_code=400, detail=f"Article cannot be submitted from status {article.status.value}"
        )
    article.status = ArticleStatus.WAITING_APPROVAL
    article.submitted_by = current_user.id
    if body.note:
        article.review_note = body.note
    await db.commit()
    await db.refresh(article)
    return article


@router.post("/{article_id}/decision", response_model=ArticleRead,
             dependencies=[Depends(require_admin)])
async def approval_decision(
    db: DBSession,
    current_user: CurrentUser,
    arq: ArqDep,
    article_id: uuid.UUID,
    body: ApprovalDecisionRequest,
) -> Article:
    """Workflow 10: administrator approves / returns / holds / rejects."""
    article = await _get_article(db, article_id)
    if article.status != ArticleStatus.WAITING_APPROVAL:
        raise HTTPException(status_code=400, detail="Article is not awaiting approval")

    decision = body.decision.lower()
    article.reviewed_by = current_user.id
    article.review_note = body.note

    if decision == "approve":
        article.status = ArticleStatus.APPROVED
        # Workflow 11: create WordPress draft job.
        await job_service.create_job(
            db, arq, job_type=JobType.WORDPRESS_DRAFT,
            article_id=article.id, created_by=current_user.id,
        )
    elif decision == "return":
        article.status = ArticleStatus.RETURNED
    elif decision == "hold":
        article.status = ArticleStatus.ON_HOLD
    elif decision == "reject":
        article.status = ArticleStatus.REJECTED
    else:
        raise HTTPException(status_code=400, detail="Invalid decision")

    await db.commit()
    await db.refresh(article)
    return article


@router.get("/pending", response_model=list[ArticleRead], dependencies=[Depends(require_admin)])
async def pending_approvals(db: DBSession) -> list[Article]:
    result = await db.execute(
        select(Article)
        .where(Article.status == ArticleStatus.WAITING_APPROVAL)
        .order_by(Article.updated_at.desc())
    )
    return list(result.scalars().all())
