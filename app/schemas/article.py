from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.enums import ArticleStatus, RegenerationScope


class ArticleVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_no: int
    title: str
    introduction: str
    headings: list
    body: str
    rendered_html: str = ""
    excerpt: str
    category_suggestion: Optional[str]
    tag_suggestions: list
    regeneration_scope: Optional[str]
    regeneration_instruction: Optional[str]
    is_manual_edit: bool
    validation_outcome: Optional[str]
    validation_result: dict
    similarity_score: Optional[float]
    created_at: datetime


class ArticleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    purchase_id: uuid.UUID
    store_id: uuid.UUID
    status: ArticleStatus
    current_version_id: Optional[uuid.UUID]
    latest_similarity_score: Optional[float]
    wordpress_post_id: Optional[int]
    published_url: Optional[str]
    published_at: Optional[datetime]
    review_note: Optional[str]
    created_at: datetime
    updated_at: datetime
    current_version: Optional[ArticleVersionRead] = None


class GenerateArticleRequest(BaseModel):
    """Trigger article generation (workflow 5). Product info must be confirmed."""

    user_instructions: Optional[str] = None


class RegenerateRequest(BaseModel):
    scope: RegenerationScope = RegenerationScope.FULL
    instruction: Optional[str] = None
    # For SECTION scope: which heading/section to regenerate.
    target_section: Optional[str] = None


class ArticleEditRequest(BaseModel):
    """Minor manual edits create a new version (history preserved)."""

    title: Optional[str] = None
    introduction: Optional[str] = None
    headings: Optional[list] = None
    body: Optional[str] = None
    rendered_html: Optional[str] = None
    excerpt: Optional[str] = None
    category_suggestion: Optional[str] = None
    tag_suggestions: Optional[list] = None


class SubmitForApprovalRequest(BaseModel):
    note: Optional[str] = None


class ApprovalDecisionRequest(BaseModel):
    decision: str  # approve | return | hold | reject
    note: Optional[str] = None
