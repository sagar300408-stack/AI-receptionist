import uuid
from sqlalchemy import Column, String, Text, DateTime, JSON, ForeignKey
from app.core.database import Base
from app.models.session import GUID

class UserResponseORM(Base):
    __tablename__ = "user_responses"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    session_id = Column(GUID, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_key = Column(String(100), nullable=False)
    question_text = Column(String(500), nullable=False)
    raw_answer = Column(Text, nullable=False)
    parsed_data = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)
