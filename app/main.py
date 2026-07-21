"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.redis import close_arq_pool

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("Starting %s (%s)", settings.APP_NAME, settings.ENVIRONMENT)
    try:
        from app.core.storage import storage

        await storage.ensure_bucket()
    except Exception as exc:  # pragma: no cover
        logger.warning("Storage bucket check failed (continuing): %s", exc)
    yield
    await close_arq_pool()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=__version__,
    description=(
        "CORE FIGHTER backend - AI article draft generation, review, approval "
        "and WordPress publication for second-hand goods buyback."
    ),
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url="/docs",
    lifespan=lifespan,
)

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "app": settings.APP_NAME, "version": __version__}


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
