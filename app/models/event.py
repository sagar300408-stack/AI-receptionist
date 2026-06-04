import uuid
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey
from app.core.database import Base
from app.models.session import GUID

class SessionEventORM(Base):
    __tablename__ = "session_events"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    session_id = Column(GUID, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    timestamp = Column(DateTime(timezone=True), nullable=False)
