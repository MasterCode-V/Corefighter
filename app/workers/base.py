"""Core job dispatcher shared by all workers.

`process_job` is the single ARQ task. It loads the DB Job row (source of
truth), transitions its status following the unified flow (workflow 16),
dispatches to the correct handler and manages retries.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionFactory
from app.core.logging import get_logger
from app.enums import JobStatus, JobType, LogLevel
from app.models import Job
from app.workers.logging_service import write_log

logger = get_logger("worker")


async def _get_handler(job_type: JobType):
    # Imported lazily to avoid circular imports at module load.
    from app.workers import handlers

    return {
        JobType.IMAGE_ANALYSIS: handlers.handle_image_analysis,
        JobType.ARTICLE_GENERATION: handlers.handle_article_generation,
        JobType.REGENERATION: handlers.handle_regeneration,
        JobType.SIMILARITY_CHECK: handlers.handle_similarity_check,
        JobType.WORDPRESS_DRAFT: handlers.handle_wordpress_draft,
        JobType.WORDPRESS_UPDATE: handlers.handle_wordpress_update,
        JobType.WORDPRESS_PUBLISH: handlers.handle_wordpress_publish,
        JobType.WORDPRESS_SYNC: handlers.handle_wordpress_sync,
    }.get(job_type)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def process_job(ctx: dict, job_id: str) -> dict:
    """ARQ entrypoint. `ctx` carries the arq redis pool for re-enqueue."""
    async with AsyncSessionFactory() as db:
        job = await db.get(Job, uuid.UUID(job_id))
        if job is None:
            logger.warning("Job %s not found", job_id)
            return {"status": "not_found"}

        if job.status == JobStatus.CANCELLED:
            logger.info("Job %s cancelled, skipping", job_id)
            return {"status": "cancelled"}

        handler = await _get_handler(job.job_type)
        if handler is None:
            job.status = JobStatus.FAILED
            job.error = f"No handler for job type {job.job_type}"
            await db.commit()
            return {"status": "failed", "error": job.error}

        job.status = JobStatus.RUNNING
        job.attempts += 1
        job.started_at = job.started_at or _now()
        await db.commit()

        try:
            result = await handler(db, job, ctx)
            job.status = JobStatus.COMPLETED
            job.result = result or {}
            job.finished_at = _now()
            await write_log(
                db, level=LogLevel.INFO, category=job.job_type.value,
                message=f"{job.job_type.value} completed",
                article_id=job.article_id, job_id=job.id,
            )
            await db.commit()
            logger.info("Job %s (%s) completed", job_id, job.job_type.value)
            return {"status": "completed", "result": result}

        except Exception as exc:  # noqa: BLE001 - jobs must never crash the worker
            await db.rollback()
            job = await db.get(Job, uuid.UUID(job_id))
            error_text = f"{type(exc).__name__}: {exc}"
            logger.exception("Job %s (%s) failed: %s", job_id, job.job_type.value, error_text)

            if job.attempts < job.max_attempts:
                job.status = JobStatus.RETRYING
                job.error = error_text
                await write_log(
                    db, level=LogLevel.WARNING, category=job.job_type.value,
                    message=f"Retrying ({job.attempts}/{job.max_attempts}): {error_text}",
                    article_id=job.article_id, job_id=job.id,
                )
                await db.commit()
                arq = ctx.get("redis")
                if arq is not None:
                    await arq.enqueue_job(
                        "process_job", job_id,
                        _defer_by=settings.JOB_RETRY_DELAY_SECONDS,
                    )
                return {"status": "retrying", "attempt": job.attempts}

            job.status = JobStatus.FAILED
            job.error = error_text
            job.finished_at = _now()
            await _on_final_failure(db, job)
            await write_log(
                db, level=LogLevel.ERROR, category=job.job_type.value,
                message=f"Job failed permanently: {error_text}",
                article_id=job.article_id, job_id=job.id,
            )
            await db.commit()
            return {"status": "failed", "error": error_text}


async def _on_final_failure(db: AsyncSession, job: Job) -> None:
    """Apply entity-level failure states (e.g. WordPress error, workflow 14)."""
    from app.enums import ArticleStatus, PurchaseStatus
    from app.models import Article, Purchase

    wp_types = {
        JobType.WORDPRESS_DRAFT, JobType.WORDPRESS_UPDATE, JobType.WORDPRESS_PUBLISH,
    }
    if job.job_type in wp_types and job.article_id:
        article = await db.get(Article, job.article_id)
        if article:
            article.status = ArticleStatus.WORDPRESS_ERROR
    if job.job_type in {JobType.IMAGE_ANALYSIS, JobType.ARTICLE_GENERATION} and job.purchase_id:
        purchase = await db.get(Purchase, job.purchase_id)
        if purchase:
            purchase.status = PurchaseStatus.FAILED
