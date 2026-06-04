from datetime import datetime, timezone
from typing import Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class BusinessHealthAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    communication_health: int
    automation_health: int
    operational_health: int
    growth_readiness: int
    facts: Dict[str, Any] = Field(default_factory=dict)
    health_assessment_version: str = "1.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
