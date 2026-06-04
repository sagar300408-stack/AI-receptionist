from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class ReportTemplate(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    industry: str
    structure: Dict[str, Any] = Field(default_factory=dict)
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BusinessReport(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    evaluation_id: UUID
    template_id: Optional[UUID] = None
    structured_data: Dict[str, Any] = Field(default_factory=dict)
    narrative_summary: Optional[str] = None
    engine_version: str = "1.0"
    qualification_version: str = "1.0"
    health_assessment_version: str = "1.0"
    narrative_version: str = "1.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ReportVersion(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    report_id: UUID
    version_number: int
    structured_data: Dict[str, Any]
    narrative_summary: Optional[str] = None
    engine_version: str
    qualification_version: str
    health_assessment_version: str
    narrative_version: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
