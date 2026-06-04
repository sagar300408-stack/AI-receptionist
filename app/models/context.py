import uuid
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey
from app.core.database import Base
from app.models.session import GUID

class BusinessContextORM(Base):
    __tablename__ = "business_contexts"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    session_id = Column(GUID, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    context_version = Column(String(50), nullable=False) # e.g., v1, v2
    generated_by = Column(String(150), nullable=False) # Name of classifier
    facts = Column(JSON, nullable=False, default=dict) # Calculated insights
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
