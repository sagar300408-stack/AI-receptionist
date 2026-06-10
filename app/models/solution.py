import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, JSON
from app.core.database import Base
from app.models.session import GUID

class SolutionCatalogORM(Base):
    __tablename__ = "solution_catalog"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(150), unique=True, nullable=False)
    solution_type = Column(String(100), nullable=False)
    description = Column(String(500), nullable=False)
    supported_constraints = Column(JSON, nullable=False, default=list)  # JSON list of constraint categories
    supported_industries = Column(JSON, nullable=False, default=list)    # JSON list of industries
    minimum_applicability = Column(Integer, nullable=False, default=40)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

class RecommendedSolutionORM(Base):
    __tablename__ = "recommended_solutions"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    session_id = Column(GUID, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    constraint_id = Column(GUID, ForeignKey("constraints.id", ondelete="CASCADE"), nullable=False, index=True)
    solution_type = Column(String(100), nullable=False)
    confidence = Column(Integer, nullable=False)
    priority_score = Column(Integer, nullable=False)
    reasoning = Column(String(500), nullable=False)
    evidence = Column(JSON, nullable=False, default=list)  # List of dicts (source, value, reason)
    created_at = Column(DateTime(timezone=True), nullable=False)
