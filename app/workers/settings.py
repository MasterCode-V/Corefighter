"""ARQ worker configuration.

Run with:  arq app.workers.settings.WorkerSettings
"""
from __future__ import annotations

from arq import cron

from app.core.database import AsyncSessionFactory
from app.core.logging import configure_logging, get_logger
from app.core.redis import get_redis_settings
from app.core.storage import storage
from app.enums import JobType
from app.workers.base import process_job

logger = get_logger("worker.settings")


async def scheduled_corpus_sync(ctx: dict) -> dict:
    """Workflow 15: scheduled historical WordPress synchronization."""
    from app.services import job_service

    async with AsyncSessionFactory() as db:
        job = await job_service.create_job(
            db, ctx["redis"], job_type=JobType.WORDPRESS_SYNC, payload={"wordpress_site_id": None}
        )
    logger.info("Scheduled corpus sync enqueued as job %s", job.id)
    return {"job_id": str(job.id)}


async def on_startup(ctx: dict) -> None:
    configure_logging()
    try:
        await storage.ensure_bucket()
    except Exception as exc:  # pragma: no cover - storage may be external
        logger.warning("Could not ensure storage bucket: %s", exc)
    logger.info("Worker started")


async def on_shutdown(ctx: dict) -> None:
    logger.info("Worker shutting down")


class WorkerSettings:
    functions = [process_job]
    cron_jobs = [
        # Run daily at 03:00 to keep the similarity corpus fresh.
        cron(scheduled_corpus_sync, hour=3, minute=0),
    ]
    redis_settings = get_redis_settings()
    on_startup = on_startup
    on_shutdown = on_shutdown
    max_jobs = 10
    job_timeout = 600  # seconds
    keep_result = 3600
    max_tries = 1  # retries are handled explicitly by process_job
