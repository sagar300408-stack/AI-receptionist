from typing import List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

class ReviewSessionSchema(BaseModel):
    id: UUID
    session_id: UUID
    reviewer: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class ReviewAuditLogSchema(BaseModel):
    id: UUID
    review_id: UUID
    action: str
    old_state: Optional[str] = None
    new_state: str
    timestamp: datetime

    class Config:
        from_attributes = True

class FounderReviewSchema(BaseModel):
    id: UUID
    review_session_id: UUID
    recommendation_id: UUID
    review_status: str
    review_decision: Optional[str] = None
    decision_reason: Optional[str] = None
    priority_level: Optional[str] = None
    priority_score: Optional[int] = None
    commercial_readiness: Optional[str] = None
    pattern_classification: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class FounderFeedbackSchema(BaseModel):
    id: UUID
    review_id: UUID
    comment: Optional[str] = None
    decision_reason: Optional[str] = None
    evidence_notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ReviewSessionResponseSchema(BaseModel):
    session: ReviewSessionSchema
    reviews: List[FounderReviewSchema] = Field(default_factory=list)

    class Config:
        from_attributes = True

# Action requests
class StartSessionRequest(BaseModel):
    reviewer: str = Field(..., description="Name or role of the reviewer starting the session")

class ApproveRequest(BaseModel):
    reviewer: Optional[str] = Field(None, description="Optional overridden reviewer name")
    priority_score: Optional[int] = Field(None, description="Fine-grained priority score from 0 to 100")
    priority_level: Optional[str] = Field(None, description="HIGH, MEDIUM, or LOW priority level")
    commercial_readiness: Optional[str] = Field(None, description="READY_FOR_PROPOSAL or NOT_READY")
    decision_reason: Optional[str] = Field(None, description="Standardized enum value for decision reason")
    comment: Optional[str] = Field(None, description="Founder's comment on approval")
    evidence_notes: Optional[str] = Field(None, description="Founder's notes on evidence validation")

class RejectRequest(BaseModel):
    decision_reason: str = Field(..., description="Standardized enum value for rejection reason")
    comment: Optional[str] = Field(None, description="Founder's comment explaining rejection")
    evidence_notes: Optional[str] = Field(None, description="Founder's notes on validation gaps")

class ResearchRequest(BaseModel):
    comment: Optional[str] = Field(None, description="Reason why further research is required")

class ArchiveRequest(BaseModel):
    comment: Optional[str] = Field(None, description="Reason for archiving the recommendation")

class FeedbackRequest(BaseModel):
    comment: Optional[str] = Field(None, description="Institutional comment")
    decision_reason: Optional[str] = Field(None, description="Standardized decision reason category")
    evidence_notes: Optional[str] = Field(None, description="Evidence trace validation notes")
