"""Job orchestration: create DB job rows and enqueue them onto the ARQ queue.

The DB `Job` row is the source of truth. FastAPI creates it as PENDING,
enqueues an ARQ task and marks it QUEUED, then returns the job id immediately.
"""
from __future__ import annotations

import uuid
from typing import Optional

from arq.connections import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.enums import JobStatus, JobType
from app.models import Job

logger = get_logger(__name__)

# ARQ queue names, allowing separate worker pools per concern (AI vs WordPress).
QUEUE_FOR_TYPE = {
    JobType.IMAGE_ANALYSIS: "ai",
    JobType.ARTICLE_GENERATION: "ai",
    JobType.REGENERATION: "ai",
    JobType.SIMILARITY_CHECK: "ai",
    JobType.WORDPRESS_DRAFT: "wordpress",
    JobType.WORDPRESS_UPDATE: "wordpress",
    JobType.WORDPRESS_PUBLISH: "wordpress",
    JobType.WORDPRESS_SYNC: "wordpress",
}


async def create_job(
    db: AsyncSession,
    arq: ArqRedis,
    *,
    job_type: JobType,
    purchase_id: Optional[uuid.UUID] = None,
    article_id: Optional[uuid.UUID] = None,
    created_by: Optional[uuid.UUID] = None,
    payload: Optional[dict] = None,
    max_attempts: Optional[int] = None,
) -> Job:
    job = Job(
        job_type=job_type,
        status=JobStatus.PENDING,
        purchase_id=purchase_id,
        article_id=article_id,
        created_by=created_by,
        payload=payload or {},
        max_attempts=max_attempts or settings.JOB_MAX_ATTEMPTS,
        queue_name=QUEUE_FOR_TYPE.get(job_type, "default"),
    )
    db.add(job)
    await db.flush()  # obtain job.id

    arq_job = await arq.enqueue_job("process_job", str(job.id))
    job.arq_job_id = arq_job.job_id if arq_job else None
    job.status = JobStatus.QUEUED
    await db.commit()
    await db.refresh(job)
    logger.info("Enqueued %s job %s", job_type.value, job.id)
    return job


async def retry_job(db: AsyncSession, arq: ArqRedis, job: Job) -> Job:
    """Manual retry (e.g. WordPress failure - workflow 14)."""
    job.status = JobStatus.QUEUED
    job.error = None
    await db.flush()
    arq_job = await arq.enqueue_job("process_job", str(job.id))
    job.arq_job_id = arq_job.job_id if arq_job else None
    await db.commit()
    await db.refresh(job)
    return job
