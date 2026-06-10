from typing import List, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

class ConstraintEvidenceSchema(BaseModel):
    source: str = Field(..., description="The signal field name or rule narrative identifier")
    value: Any = Field(..., description="The value of the signal at classification time")
    reason: str = Field(..., description="Human-readable reason justifying why this signal indicates a bottleneck")

    class Config:
        from_attributes = True

class ConstraintSchema(BaseModel):
    id: UUID = Field(..., description="Unique ID of the constraint")
    session_id: UUID = Field(..., description="Session ID this constraint belongs to")
    category: str = Field(..., description="Constraint bottleneck category")
    confidence: int = Field(..., description="Confidence score from 0 to 100")
    severity: str = Field(..., description="LOW, MEDIUM, HIGH, CRITICAL severity rating")
    impact_score: int = Field(..., description="Calculated impact score from 0 to 100")
    evidence: List[ConstraintEvidenceSchema] = Field(default_factory=list, description="Satisfied database criteria rules trace logs")
    origin: List[str] = Field(default_factory=list, description="List of triggering field names")
    created_at: datetime = Field(..., description="Time of constraint classification")

    class Config:
        from_attributes = True

class ConstraintDetailsResponse(BaseModel):
    session_id: UUID = Field(..., description="Session ID")
    constraints: List[ConstraintSchema] = Field(default_factory=list, description="List of identified constraints for this session")

    class Config:
        from_attributes = True
