"""Central enumerations shared across models, schemas and workers."""
from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    """Application roles and their permission tiers."""

    ADMIN = "ADMIN"                # Full access, approves & publishes
    STORE_MANAGER = "STORE_MANAGER"  # Manages a single store, submits for approval
    STORE_STAFF = "STORE_STAFF"    # Registers purchases, generates & edits drafts


class ImageType(str, Enum):
    ARTICLE = "ARTICLE"    # Main / eye-catch image
    DETAIL = "DETAIL"      # Supplementary detail images


class PurchaseStatus(str, Enum):
    UNSTARTED = "UNSTARTED"
    IMAGE_ANALYSIS_QUEUED = "IMAGE_ANALYSIS_QUEUED"
    IMAGE_ANALYSIS_RUNNING = "IMAGE_ANALYSIS_RUNNING"
    ANALYZED = "ANALYZED"
    GENERATION_QUEUED = "GENERATION_QUEUED"
    GENERATION_RUNNING = "GENERATION_RUNNING"
    ARTICLE_READY = "ARTICLE_READY"
    FAILED = "FAILED"


class ArticleStatus(str, Enum):
    """Full lifecycle of a generated article (workflows 5-15)."""

    DRAFT = "DRAFT"                        # Freshly generated
    NEEDS_CORRECTION = "NEEDS_CORRECTION"  # Validation failed
    SIMILARITY_WARNING = "SIMILARITY_WARNING"
    WAITING_LIST = "WAITING_LIST"          # Publication waiting list
    WAITING_APPROVAL = "WAITING_APPROVAL"
    RETURNED = "RETURNED"
    ON_HOLD = "ON_HOLD"
    REJECTED = "REJECTED"
    APPROVED = "APPROVED"
    WORDPRESS_DRAFT = "WORDPRESS_DRAFT"
    WORDPRESS_ERROR = "WORDPRESS_ERROR"
    PUBLISHED = "PUBLISHED"


class JobType(str, Enum):
    IMAGE_ANALYSIS = "IMAGE_ANALYSIS"
    ARTICLE_GENERATION = "ARTICLE_GENERATION"
    SIMILARITY_CHECK = "SIMILARITY_CHECK"
    REGENERATION = "REGENERATION"
    WORDPRESS_DRAFT = "WORDPRESS_DRAFT"
    WORDPRESS_UPDATE = "WORDPRESS_UPDATE"
    WORDPRESS_PUBLISH = "WORDPRESS_PUBLISH"
    WORDPRESS_SYNC = "WORDPRESS_SYNC"


class JobStatus(str, Enum):
    """Unified job status flow (workflow 16)."""

    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"


class RegenerationScope(str, Enum):
    FULL = "FULL"
    TITLE = "TITLE"
    INTRODUCTION = "INTRODUCTION"
    SECTION = "SECTION"
    DIFFERENT_TONE = "DIFFERENT_TONE"
    MORE_DIFFERENT = "MORE_DIFFERENT"  # Greater difference from past articles


class ValidationOutcome(str, Enum):
    PASSED = "PASSED"
    WARNING = "WARNING"
    FAILED = "FAILED"


class ContentRuleType(str, Enum):
    PROHIBITED_WORD = "PROHIBITED_WORD"
    PROHIBITED_CONTEXT = "PROHIBITED_CONTEXT"
    BRAND_RULE = "BRAND_RULE"
    STRUCTURE = "STRUCTURE"


class LogLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
