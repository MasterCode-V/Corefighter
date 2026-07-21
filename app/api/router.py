from fastapi import APIRouter

from app.api.v1 import (
    approval,
    articles,
    auth,
    content_rules,
    dashboard,
    jobs,
    media,
    personas,
    purchases,
    stores,
    users,
    wordpress,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(stores.router, prefix="/stores", tags=["stores"])
api_router.include_router(personas.router, prefix="/personas", tags=["personas"])
api_router.include_router(content_rules.router, prefix="/content-rules", tags=["content-rules"])
api_router.include_router(purchases.router, prefix="/purchases", tags=["purchases"])
api_router.include_router(articles.router, prefix="/articles", tags=["articles"])
api_router.include_router(approval.router, prefix="/approval", tags=["approval"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(wordpress.router, prefix="/wordpress", tags=["wordpress"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(media.router, prefix="/media", tags=["media"])
