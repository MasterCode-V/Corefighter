from __future__ import annotations

import uuid
from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict


class SimilarityResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    article_id: uuid.UUID
    article_version_id: uuid.UUID
    similarity_score: float
    semantic_score: float
    text_score: float
    passed: bool
    most_similar: List[dict]
    repeated_sections: List[dict]
    created_at: datetime
