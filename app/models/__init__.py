"""SQLAlchemy models. Importing this package registers all tables on Base."""
from app.models.base import Base
from app.models.user import User
from app.models.store import Store, WordPressSite
from app.models.persona import Persona
from app.models.content_rule import ContentRule
from app.models.purchase import Purchase, PurchaseImage
from app.models.article import Article, ArticleVersion
from app.models.embedding import PublishedCorpus, CorpusEmbedding
from app.models.similarity import SimilarityResult
from app.models.job import Job
from app.models.log import ActivityLog

__all__ = [
    "Base",
    "User",
    "Store",
    "WordPressSite",
    "Persona",
    "ContentRule",
    "Purchase",
    "PurchaseImage",
    "Article",
    "ArticleVersion",
    "PublishedCorpus",
    "CorpusEmbedding",
    "SimilarityResult",
    "Job",
    "ActivityLog",
]
