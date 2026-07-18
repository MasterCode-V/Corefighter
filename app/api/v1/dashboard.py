from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.core.deps import CurrentUser, DBSession
from app.enums import ArticleStatus, JobStatus, LogLevel, UserRole
from app.models import Article, ActivityLog, Job, Purchase
from app.schemas.job import JobRead

router = APIRouter()


@router.get("/summary")
async def dashboard_summary(db: DBSession, current_user: CurrentUser) -> dict:
    """Aggregate counts for the admin dashboard (workflow: dashboard data)."""
    store_scoped = current_user.role != UserRole.ADMIN and current_user.store_id

    article_stmt = select(Article.status, func.count()).group_by(Article.status)
    purchase_stmt = select(Purchase.status, func.count()).group_by(Purchase.status)
    if store_scoped:
        article_stmt = article_stmt.where(Article.store_id == current_user.store_id)
        purchase_stmt = purchase_stmt.where(Purchase.store_id == current_user.store_id)

    articles_by_status = {
        status.value: count for status, count in (await db.execute(article_stmt)).all()
    }
    purchases_by_status = {
        status.value: count for status, count in (await db.execute(purchase_stmt)).all()
    }
    jobs_by_status = {
        status.value: count
        for status, count in (
            await db.execute(select(Job.status, func.count()).group_by(Job.status))
        ).all()
    }

    return {
        "articles_by_status": articles_by_status,
        "purchases_by_status": purchases_by_status,
        "jobs_by_status": jobs_by_status,
        "waiting_approval": articles_by_status.get(ArticleStatus.WAITING_APPROVAL.value, 0),
        "waiting_list": articles_by_status.get(ArticleStatus.WAITING_LIST.value, 0),
        "published": articles_by_status.get(ArticleStatus.PUBLISHED.value, 0),
        "failed_jobs": jobs_by_status.get(JobStatus.FAILED.value, 0),
    }


@router.get("/logs")
async def activity_logs(
    db: DBSession,
    current_user: CurrentUser,
    level: Optional[LogLevel] = None,
    category: Optional[str] = None,
    article_id: Optional[uuid.UUID] = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
) -> list[dict]:
    """Workflow: posting/error history."""
    stmt = select(ActivityLog)
    if level:
        stmt = stmt.where(ActivityLog.level == level)
    if category:
        stmt = stmt.where(ActivityLog.category == category)
    if article_id:
        stmt = stmt.where(ActivityLog.article_id == article_id)
    stmt = stmt.order_by(ActivityLog.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    logs = result.scalars().all()
    return [
        {
            "id": str(log.id),
            "level": log.level.value,
            "category": log.category,
            "message": log.message,
            "article_id": str(log.article_id) if log.article_id else None,
            "job_id": str(log.job_id) if log.job_id else None,
            "payload": log.payload,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


@router.get("/recent-jobs", response_model=list[JobRead])
async def recent_jobs(db: DBSession, current_user: CurrentUser, limit: int = 20) -> list[Job]:
    result = await db.execute(select(Job).order_by(Job.created_at.desc()).limit(limit))
    return list(result.scalars().all())
