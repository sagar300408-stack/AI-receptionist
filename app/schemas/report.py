from typing import List, Dict, Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field

class QualificationSchema(BaseModel):
    score: int
    grade: str
    routing_path: str

class HealthIndexSchema(BaseModel):
    communication_health: int
    automation_health: int
    operational_health: int
    growth_readiness: int

class ConsultationRecommendationSchema(BaseModel):
    recommended: bool
    confidence: float
    reasons: List[str]

class NarrativeEvidenceMappingSchema(BaseModel):
    paragraph_index: int
    evidence_id: UUID
    fields: List[str]

class ReportDetailsResponse(BaseModel):
    report_id: UUID
    version: int
    template_name: str
    qualification: QualificationSchema
    health_index: HealthIndexSchema
    consultation: ConsultationRecommendationSchema
    structured_data: Dict[str, Any]
    narrative_summary: str
    narrative_evidence: List[NarrativeEvidenceMappingSchema]
