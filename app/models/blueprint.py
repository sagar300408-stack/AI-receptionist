import uuid
from sqlalchemy import Column, String, Boolean, DateTime, JSON
from app.core.database import Base
from app.models.session import GUID

class DiscoveryBlueprintORM(Base):
    __tablename__ = "discovery_blueprints"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(150), nullable=False)
    industry = Column(String(100), nullable=False)
    version = Column(String(20), nullable=False, default="v1")
    stages = Column(JSON, nullable=False, default=list) # Sequence list e.g., ["Business", "Lead Flow"]
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
