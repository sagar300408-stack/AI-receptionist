import uuid
from sqlalchemy import Column, String, Integer, Boolean, JSON
from app.core.database import Base
from app.models.session import GUID

class QuestionTemplateORM(Base):
    __tablename__ = "question_templates"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    question_key = Column(String(100), nullable=False, unique=True, index=True)
    question_text = Column(String(500), nullable=False)
    industry = Column(String(100), nullable=True) # Nullable implies generic/cross-industry
    preconditions = Column(JSON, nullable=False, default=dict) # Evaluation logic conditions
    priority = Column(Integer, nullable=False, default=100) # Lower priority evaluated first
    required = Column(Boolean, nullable=False, default=True)
    active = Column(Boolean, nullable=False, default=True)
