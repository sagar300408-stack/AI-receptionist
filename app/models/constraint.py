import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, JSON
from app.core.database import Base
from app.models.session import GUID

class ConstraintRuleORM(Base):
    __tablename__ = "constraint_rules"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(150), unique=True, nullable=False)
    category = Column(String(100), nullable=False)
    conditions = Column(JSON, nullable=False, default=dict)
    base_confidence = Column(Integer, nullable=False)
    severity = Column(String(50), nullable=False)
    base_impact = Column(Integer, nullable=False)
    evidence_template = Column(String(500), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

class ConstraintORM(Base):
    __tablename__ = "constraints"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    session_id = Column(GUID, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(100), nullable=False)
    confidence = Column(Integer, nullable=False)
    severity = Column(String(50), nullable=False)
    impact_score = Column(Integer, nullable=False)
    evidence = Column(JSON, nullable=False, default=list) # List of dicts: source, value, reason
    origin = Column(JSON, nullable=False, default=list) # List of strings
    created_at = Column(DateTime(timezone=True), nullable=False)
