from enum import Enum
from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field

class ReviewSessionStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    UNDER_REVIEW = "UNDER_REVIEW"
    COMPLETED = "COMPLETED"

class ReviewStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_RESEARCH = "NEEDS_RESEARCH"
    ARCHIVED = "ARCHIVED"

class CommercialReadiness(str, Enum):
    READY_FOR_PROPOSAL = "READY_FOR_PROPOSAL"
    NOT_READY = "NOT_READY"

class PriorityLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class ReviewDecisionReason(str, Enum):
    APPROVED = "APPROVED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    LOW_ROI = "LOW_ROI"
    DUPLICATE_OPPORTUNITY = "DUPLICATE_OPPORTUNITY"
    HIGH_RISK = "HIGH_RISK"
    NOT_AI_SOLVABLE = "NOT_AI_SOLVABLE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"

class PatternClassification(str, Enum):
    OPPORTUNITY_TEMPLATE = "OPPORTUNITY_TEMPLATE"
    OPPORTUNITY_VARIANT = "OPPORTUNITY_VARIANT"
    NET_NEW_OPPORTUNITY = "NET_NEW_OPPORTUNITY"

class ReviewSession(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    reviewer: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: ReviewSessionStatus = ReviewSessionStatus.PENDING_REVIEW
    created_at: datetime = Field(default_factory=datetime.now)

class FounderReview(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    review_session_id: UUID
    recommendation_id: UUID
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    review_decision: Optional[str] = None
    decision_reason: Optional[ReviewDecisionReason] = None
    priority_level: Optional[PriorityLevel] = None
    priority_score: Optional[int] = None
    commercial_readiness: Optional[CommercialReadiness] = None
    pattern_classification: Optional[PatternClassification] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class FounderFeedback(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    review_id: UUID
    comment: Optional[str] = None
    decision_reason: Optional[ReviewDecisionReason] = None
    evidence_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

class ReviewAuditLog(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    review_id: UUID
    action: str
    old_state: Optional[str] = None
    new_state: str
    timestamp: datetime = Field(default_factory=datetime.now)

class ReviewLifecyclePolicy:
    """Enforces state transition rules for Review Sessions and Founder Reviews."""

    @staticmethod
    def validate_session_transition(old_state: ReviewSessionStatus, new_state: ReviewSessionStatus) -> bool:
        if old_state == new_state:
            return True

        allowed = {
            ReviewSessionStatus.PENDING_REVIEW: {ReviewSessionStatus.UNDER_REVIEW, ReviewSessionStatus.COMPLETED},
            ReviewSessionStatus.UNDER_REVIEW: {ReviewSessionStatus.COMPLETED},
            ReviewSessionStatus.COMPLETED: set()  # Terminal state
        }

        if new_state not in allowed.get(old_state, set()):
            raise ValueError(f"Invalid ReviewSession transition from {old_state} to {new_state}.")
        return True

    @staticmethod
    def validate_review_transition(old_state: ReviewStatus, new_state: ReviewStatus) -> bool:
        if old_state == new_state:
            return True

        allowed = {
            ReviewStatus.PENDING_REVIEW: {
                ReviewStatus.UNDER_REVIEW,
                ReviewStatus.APPROVED,
                ReviewStatus.REJECTED,
                ReviewStatus.NEEDS_RESEARCH
            },
            ReviewStatus.UNDER_REVIEW: {
                ReviewStatus.APPROVED,
                ReviewStatus.REJECTED,
                ReviewStatus.NEEDS_RESEARCH
            },
            ReviewStatus.NEEDS_RESEARCH: {
                ReviewStatus.UNDER_REVIEW,
                ReviewStatus.APPROVED,
                ReviewStatus.REJECTED
            },
            ReviewStatus.APPROVED: {ReviewStatus.ARCHIVED},
            ReviewStatus.REJECTED: {ReviewStatus.ARCHIVED},
            ReviewStatus.ARCHIVED: set()  # Terminal state
        }

        if new_state not in allowed.get(old_state, set()):
            raise ValueError(f"Invalid FounderReview transition from {old_state} to {new_state}.")
        return True
