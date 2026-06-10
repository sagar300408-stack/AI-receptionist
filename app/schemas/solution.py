from typing import List, Any, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

class SolutionEvidenceSchema(BaseModel):
    source: str = Field(..., description="The signal field name or rule narrative identifier")
    value: Any = Field(..., description="The value of the signal at evaluation time")
    reason: str = Field(..., description="Human-readable reason justifying solution recommendation")

    class Config:
        from_attributes = True

class RecommendedSolutionSchema(BaseModel):
    id: UUID = Field(..., description="Unique ID of the recommended solution")
    session_id: UUID = Field(..., description="Session ID")
    constraint_id: UUID = Field(..., description="Constraint ID evaluated")
    solution_type: str = Field(..., description="SolutionType enum value")
    confidence: int = Field(..., description="Confidence score from 0 to 100")
    priority_score: int = Field(..., description="Priority score calculated")
    reasoning: str = Field(..., description="Human-readable explanation of why the solution is recommended")
    evidence: List[SolutionEvidenceSchema] = Field(default_factory=list, description="List of evidence metrics")
    created_at: datetime = Field(..., description="Evaluation timestamp")

    class Config:
        from_attributes = True

class SolutionResponse(BaseModel):
    session_id: UUID = Field(..., description="Session ID")
    results: List[RecommendedSolutionSchema] = Field(default_factory=list, description="Recommended solutions list")

    class Config:
        from_attributes = True
