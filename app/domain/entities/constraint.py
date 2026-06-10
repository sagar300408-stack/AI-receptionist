from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from app.domain.value_objects.constraint import ConstraintCategory, ConstraintEvidence

class ConstraintRule(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    category: ConstraintCategory
    conditions: Dict[str, Any]
    base_confidence: int
    severity: str
    base_impact: int
    evidence_template: str
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)

class Constraint(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    category: ConstraintCategory
    confidence: int
    severity: str
    impact_score: int
    evidence: List[ConstraintEvidence] = Field(default_factory=list)
    origin: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
