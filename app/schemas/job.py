from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.enums import JobStatus, JobType


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_type: JobType
    status: JobStatus
    purchase_id: Optional[uuid.UUID]
    article_id: Optional[uuid.UUID]
    payload: dict
    result: dict
    error: Optional[str]
    attempts: int
    max_attempts: int
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]


class JobCreatedResponse(BaseModel):
    """Returned immediately when FastAPI enqueues a background job."""

    job_id: uuid.UUID
    job_type: JobType
    status: JobStatus
