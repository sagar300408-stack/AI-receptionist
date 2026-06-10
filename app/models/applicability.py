import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, JSON
from app.core.database import Base
from app.models.session import GUID

class ApplicabilityRuleORM(Base):
    __tablename__ = "applicability_rules"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(150), unique=True, nullable=False)
    version = Column(String(50), nullable=False, default="1.0")
    constraint_category = Column(String(100), nullable=False)
    conditions = Column(JSON, nullable=False, default=dict)
    applicability_score = Column(Integer, nullable=False)
    confidence = Column(Integer, nullable=False)
    category = Column(String(100), nullable=False)
    reasoning_template = Column(String(500), nullable=False)
    recommended_solution_types = Column(JSON, nullable=False, default=list)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

class AIApplicabilityORM(Base):
    __tablename__ = "ai_applicability"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    session_id = Column(GUID, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    constraint_id = Column(GUID, ForeignKey("constraints.id", ondelete="CASCADE"), nullable=False, index=True)
    applicability_score = Column(Integer, nullable=False)
    confidence = Column(Integer, nullable=False)
    category = Column(String(100), nullable=False)
    reasoning = Column(String(500), nullable=False)
    evidence = Column(JSON, nullable=False, default=list) # List of dicts (source, value, reason)
    recommended_solution_types = Column(JSON, nullable=False, default=list) # List of SolutionType string values
    rule_version = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

class ReviewQueueORM(Base):
    __tablename__ = "manual_review_queue"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    session_id = Column(GUID, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    constraint_id = Column(GUID, ForeignKey("constraints.id", ondelete="SET NULL"), nullable=True, index=True)
    reason = Column(String(500), nullable=False)
    priority = Column(String(50), nullable=False) # e.g. "HIGH", "MEDIUM", "LOW"
    created_at = Column(DateTime(timezone=True), nullable=False)
