from datetime import datetime, timezone
from typing import List, Optional, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from app.domain.value_objects.opportunity import Priority

class OpportunityEvidence(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    result_id: UUID
    field: str
    value: Any
    operator: str
    rule_expression: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class OpportunityResult(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    evaluation_id: UUID
    template_id: UUID
    priority: Priority
    confidence: float
    impact_score: int
    complexity_score: int
    reasoning: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class OpportunityEvaluation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    scoring_profile_id: Optional[UUID] = None
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    engine_version: str = "1.0"
    ruleset_version: str = "2026.06.04"
