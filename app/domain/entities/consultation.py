from datetime import datetime, timezone
from typing import List
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class ConsultationRecommendation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    consultation_recommended: bool
    confidence: float
    reasons: List[str] = Field(default_factory=list)
    consultation_version: str = "1.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
