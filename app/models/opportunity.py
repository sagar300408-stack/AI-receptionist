import uuid
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, JSON, ForeignKey
from app.core.database import Base
from app.models.session import GUID

class OpportunityGroupORM(Base):
    __tablename__ = "opportunity_groups"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(150), unique=True, nullable=False)
    category = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True)

class OpportunityTemplateORM(Base):
    __tablename__ = "opportunity_templates"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    group_id = Column(GUID, ForeignKey("opportunity_groups.id", ondelete="SET NULL"), nullable=True)
    code = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    version = Column(String(20), nullable=False, default="v1")
    description = Column(Text, nullable=True)
    base_impact = Column(Float, nullable=False, default=50.0)
    base_complexity = Column(Float, nullable=False, default=50.0)
    active = Column(Boolean, nullable=False, default=True)
    effective_from = Column(DateTime(timezone=True), nullable=True)
    effective_to = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

class OpportunityRuleORM(Base):
    __tablename__ = "opportunity_rules"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    template_id = Column(GUID, ForeignKey("opportunity_templates.id", ondelete="CASCADE"), nullable=False)
    rule_type = Column(String(50), nullable=False) # ELIGIBILITY, IMPACT_MODIFIER, COMPLEXITY_MODIFIER, REASONING
    conditions = Column(JSON, nullable=False)
    modifier_value = Column(Float, nullable=True)
    explanation_template = Column(String(500), nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

class ScoringProfileORM(Base):
    __tablename__ = "scoring_profiles"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(150), unique=True, nullable=False)
    thresholds = Column(JSON, nullable=False) # critical: {impact: 80, complexity: 40}, etc.
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

class OpportunityEvaluationORM(Base):
    __tablename__ = "opportunity_evaluations"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    session_id = Column(GUID, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    scoring_profile_id = Column(GUID, ForeignKey("scoring_profiles.id", ondelete="SET NULL"), nullable=True)
    evaluated_at = Column(DateTime(timezone=True), nullable=False)
    engine_version = Column(String(50), nullable=False)
    ruleset_version = Column(String(50), nullable=False)

class OpportunityResultORM(Base):
    __tablename__ = "opportunity_results"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    evaluation_id = Column(GUID, ForeignKey("opportunity_evaluations.id", ondelete="CASCADE"), nullable=False, index=True)
    template_id = Column(GUID, ForeignKey("opportunity_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    priority = Column(String(50), nullable=False) # LOW, MEDIUM, HIGH, CRITICAL
    confidence = Column(Float, nullable=False, default=1.0)
    impact_score = Column(Integer, nullable=False)
    complexity_score = Column(Integer, nullable=False)
    reasoning = Column(JSON, nullable=False) # List of compiled strings
    created_at = Column(DateTime(timezone=True), nullable=False)

class OpportunityEvidenceORM(Base):
    __tablename__ = "opportunity_evidence"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    result_id = Column(GUID, ForeignKey("opportunity_results.id", ondelete="CASCADE"), nullable=False, index=True)
    field = Column(String(100), nullable=False)
    value = Column(JSON, nullable=False)
    operator = Column(String(50), nullable=False)
    rule_expression = Column(String(200), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
