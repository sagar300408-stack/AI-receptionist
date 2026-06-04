from datetime import datetime, timezone
from typing import List, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from app.domain.value_objects.report import LeadGrade, RoutingPath

class QualificationResult(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    qualification_score: int
    lead_grade: LeadGrade
    routing_path: RoutingPath
    factors: List[Dict[str, Any]] = Field(default_factory=list)
    qualification_version: str = "1.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
