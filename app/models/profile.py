import uuid
from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, ForeignKey
from app.core.database import Base
from app.models.session import GUID

class BusinessProfileORM(Base):
    __tablename__ = "business_profiles"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    session_id = Column(GUID, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    industry = Column(String(100), nullable=True)
    business_type = Column(String(100), nullable=True)
    team_size = Column(Integer, nullable=True)
    monthly_leads = Column(Integer, nullable=True)
    monthly_customers = Column(Integer, nullable=True)
    business_stage = Column(String(50), nullable=True)
    communication_channels = Column(JSON, nullable=False, default=list)
    pain_points = Column(JSON, nullable=False, default=list)
    goals = Column(JSON, nullable=False, default=list)
    profile_completion = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
