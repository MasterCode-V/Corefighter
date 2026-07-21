"""Worker handlers for each job type (workflows 4-15)."""
from app.workers.handlers.image_analysis import handle_image_analysis
from app.workers.handlers.generation import (
    handle_article_generation,
    handle_regeneration,
)
from app.workers.handlers.similarity import handle_similarity_check
from app.workers.handlers.wordpress import (
    handle_wordpress_draft,
    handle_wordpress_publish,
    handle_wordpress_sync,
    handle_wordpress_update,
)

__all__ = [
    "handle_image_analysis",
    "handle_article_generation",
    "handle_regeneration",
    "handle_similarity_check",
    "handle_wordpress_draft",
    "handle_wordpress_update",
    "handle_wordpress_publish",
    "handle_wordpress_sync",
]
