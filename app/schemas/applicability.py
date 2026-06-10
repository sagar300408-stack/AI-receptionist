from typing import List, Any, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

class ApplicabilityEvidenceSchema(BaseModel):
    source: str = Field(..., description="The signal field name or rule narrative identifier")
    value: Any = Field(..., description="The value of the signal at evaluation time")
    reason: str = Field(..., description="Human-readable reason justifying applicability")

    class Config:
        from_attributes = True

class ApplicabilitySchema(BaseModel):
    id: UUID = Field(..., description="Unique ID of the applicability result")
    session_id: UUID = Field(..., description="Session ID")
    constraint_id: UUID = Field(..., description="Constraint ID evaluated")
    applicability_score: int = Field(..., description="Applicability score from 0 to 100")
    confidence: int = Field(..., description="Confidence score from 0 to 100")
    category: str = Field(..., description="ApplicabilityCategory string value")
    reasoning: str = Field(..., description="Human-readable explanation of applicability evaluation")
    evidence: List[ApplicabilityEvidenceSchema] = Field(default_factory=list, description="List of evidence metrics")
    recommended_solution_types: List[str] = Field(default_factory=list, description="List of recommended SolutionType string values")
    rule_version: str = Field(..., description="Rule version used for evaluation")
    created_at: datetime = Field(..., description="Evaluation timestamp")

    class Config:
        from_attributes = True

class ApplicabilityResponse(BaseModel):
    session_id: UUID = Field(..., description="Session ID")
    results: List[ApplicabilitySchema] = Field(default_factory=list, description="AI applicability evaluation results")

    class Config:
        from_attributes = True

class ReviewQueueSchema(BaseModel):
    id: UUID = Field(..., description="Unique ID of the review queue item")
    session_id: UUID = Field(..., description="Session ID")
    constraint_id: Optional[UUID] = Field(None, description="Nullable Constraint ID")
    reason: str = Field(..., description="Triage audit reason")
    priority: str = Field(..., description="HIGH, MEDIUM, LOW triage urgency rating")
    created_at: datetime = Field(..., description="Triage entry timestamp")

    class Config:
        from_attributes = True
