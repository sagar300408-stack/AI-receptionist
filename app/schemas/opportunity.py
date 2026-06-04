from typing import List, Dict, Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field

class OpportunityEvidenceSchema(BaseModel):
    field: str
    value: Any
    operator: str
    rule_expression: str

    class Config:
        from_attributes = True

class OpportunityResultSchema(BaseModel):
    opportunity_code: str = Field(..., description="Unique alphanumeric code of the template")
    name: str = Field(..., description="Display name of the opportunity")
    priority: str = Field(..., description="LOW, MEDIUM, HIGH, CRITICAL priority rating")
    confidence: float = Field(..., description="Confidence score from 0.0 to 1.0")
    impact_score: int = Field(..., description="Calculated impact score from 0 to 100")
    complexity_score: int = Field(..., description="Calculated complexity score from 0 to 100")
    reasoning: List[str] = Field(default_factory=list, description="Reasoning evidence text logs")
    evidence: List[OpportunityEvidenceSchema] = Field(default_factory=list, description="Satisfied database criteria rules trace logs")

class SessionOpportunitiesResponse(BaseModel):
    evaluation_id: UUID
    engine_version: str
    ruleset_version: str
    scoring_profile: str
    groups: Dict[str, List[OpportunityResultSchema]] = Field(default_factory=dict, description="Opportunities mapped to their groups")
