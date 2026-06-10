import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON, Text
from app.core.database import Base
from app.models.session import GUID

class ReviewSessionORM(Base):
    __tablename__ = "review_sessions"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    session_id = Column(GUID, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    reviewer = Column(String(100), nullable=True)
    status = Column(String(50), nullable=False, default="PENDING_REVIEW")
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

class FounderReviewORM(Base):
    __tablename__ = "founder_reviews"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    review_session_id = Column(GUID, ForeignKey("review_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation_id = Column(GUID, ForeignKey("recommended_solutions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    review_status = Column(String(50), nullable=False, default="PENDING_REVIEW")
    review_decision = Column(String(50), nullable=True)
    decision_reason = Column(String(100), nullable=True)
    priority_level = Column(String(50), nullable=True)
    priority_score = Column(Integer, nullable=True)
    commercial_readiness = Column(String(50), nullable=True)
    pattern_classification = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

class FounderFeedbackORM(Base):
    __tablename__ = "founder_feedback"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    review_id = Column(GUID, ForeignKey("founder_reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    comment = Column(Text, nullable=True)
    decision_reason = Column(String(100), nullable=True)
    evidence_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

class ReviewAuditLogORM(Base):
    __tablename__ = "review_audit_logs"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    review_id = Column(GUID, ForeignKey("founder_reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(100), nullable=False)
    old_state = Column(String(50), nullable=True)
    new_state = Column(String(50), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
