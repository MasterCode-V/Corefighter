from __future__ import annotations

import uuid
from typing import Annotated, Optional

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.core.deps import CurrentUser, DBSession, get_arq
from app.enums import JobStatus, JobType
from app.models import Job
from app.schemas.job import JobRead
from app.services import job_service

router = APIRouter()
ArqDep = Annotated[ArqRedis, Depends(get_arq)]


@router.get("", response_model=list[JobRead])
async def list_jobs(
    db: DBSession,
    current_user: CurrentUser,
    status_filter: Optional[JobStatus] = None,
    job_type: Optional[JobType] = None,
    article_id: Optional[uuid.UUID] = None,
    purchase_id: Optional[uuid.UUID] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Job]:
    stmt = select(Job)
    if status_filter:
        stmt = stmt.where(Job.status == status_filter)
    if job_type:
        stmt = stmt.where(Job.job_type == job_type)
    if article_id:
        stmt = stmt.where(Job.article_id == article_id)
    if purchase_id:
        stmt = stmt.where(Job.purchase_id == purchase_id)
    stmt = stmt.order_by(Job.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{job_id}", response_model=JobRead)
async def get_job(db: DBSession, current_user: CurrentUser, job_id: uuid.UUID) -> Job:
    """Workflow: poll job status by id."""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/retry", response_model=JobRead)
async def retry_job(
    db: DBSession, current_user: CurrentUser, arq: ArqDep, job_id: uuid.UUID
) -> Job:
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in (JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.PARTIALLY_COMPLETED):
        raise HTTPException(status_code=400, detail="Only failed/cancelled jobs can be retried")
    return await job_service.retry_job(db, arq, job)


@router.post("/{job_id}/cancel", response_model=JobRead)
async def cancel_job(db: DBSession, current_user: CurrentUser, job_id: uuid.UUID) -> Job:
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
        raise HTTPException(status_code=400, detail="Job already finished")
    job.status = JobStatus.CANCELLED
    await db.commit()
    await db.refresh(job)
    return job
