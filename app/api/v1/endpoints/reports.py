from uuid import UUID
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db_session
from app.core.exceptions import TviraException, SessionNotFoundError
from app.models.report import (
    BusinessReportORM, ReportVersionORM, ReportNarrativeEvidenceORM,
    QualificationResultORM, BusinessHealthAssessmentORM,
    ConsultationRecommendationORM, ReportTemplateORM
)
from app.models.opportunity import OpportunityEvidenceORM
from app.schemas.report import (
    ReportDetailsResponse, QualificationSchema, HealthIndexSchema,
    ConsultationRecommendationSchema, NarrativeEvidenceMappingSchema
)
from app.services.report_service import ReportService

router = APIRouter()

@router.post("/{session_id}/report/regenerate", response_model=ReportDetailsResponse)
async def regenerate_report(
    session_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Forces recalculations of the business opportunities report, generating an archived history version."""
    try:
        service = ReportService()
        report, qual, health, consul = await service.generate_or_regenerate_report(
            db, session_id, force_regenerate=True
        )
        return await _serialize_report_response(db, session_id, report, qual, health, consul)
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except TviraException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{session_id}/report", response_model=ReportDetailsResponse)
async def get_report_details(
    session_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Retrieves the generated business opportunity report, priority matrix, and audit trace details."""
    # Fetch report
    r_query = select(BusinessReportORM).where(BusinessReportORM.session_id == session_id)
    r_result = await db.execute(r_query)
    report = r_result.scalars().first()
    
    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"No reports found for session {session_id}. Verify that discovery is complete."
        )

    # Fetch qualification
    q_query = select(QualificationResultORM).where(QualificationResultORM.session_id == session_id)
    q_result = await db.execute(q_query)
    qual = q_result.scalars().first()

    # Fetch health
    h_query = select(BusinessHealthAssessmentORM).where(BusinessHealthAssessmentORM.session_id == session_id)
    h_result = await db.execute(h_query)
    health = h_result.scalars().first()

    # Fetch booking consultation recommendation
    c_query = select(ConsultationRecommendationORM).where(ConsultationRecommendationORM.session_id == session_id)
    c_result = await db.execute(c_query)
    consul = c_result.scalars().first()

    return await _serialize_report_response(db, session_id, report, qual, health, consul)

async def _serialize_report_response(
    db: AsyncSession,
    session_id: UUID,
    report: BusinessReportORM,
    qual: QualificationResultORM,
    health: BusinessHealthAssessmentORM,
    consul: ConsultationRecommendationORM
) -> ReportDetailsResponse:
    """Helper serializer mapping ORM database entities to unified schemas."""
    
    # Get current version number by counting archive entries + 1
    v_query = select(func.count(ReportVersionORM.id)).where(ReportVersionORM.report_id == report.id)
    v_result = await db.execute(v_query)
    version_count = v_result.scalar() or 0
    current_version = version_count + 1

    # Fetch template name
    template_name = "Standard Business Report Layout"
    if report.template_id:
        t = await db.get(ReportTemplateORM, report.template_id)
        if t:
            template_name = t.name

    # Fetch narrative evidence links
    ne_query = select(ReportNarrativeEvidenceORM).where(
        ReportNarrativeEvidenceORM.report_id == report.id
    )
    ne_result = await db.execute(ne_query)
    mappings = list(ne_result.scalars().all())

    schemas_mappings = []
    for m in mappings:
        # Fetch evidence to resolve fields
        ev = await db.get(OpportunityEvidenceORM, m.evidence_id)
        fields = [ev.field] if ev else []
        schemas_mappings.append(
            NarrativeEvidenceMappingSchema(
                paragraph_index=m.paragraph_index,
                evidence_id=m.evidence_id,
                fields=fields
            )
        )

    return ReportDetailsResponse(
        report_id=report.id,
        version=current_version,
        template_name=template_name,
        qualification=QualificationSchema(
            score=qual.qualification_score if qual else 0,
            grade=qual.lead_grade if qual else "COLD",
            routing_path=qual.routing_path if qual else "SELF_SERVE"
        ),
        health_index=HealthIndexSchema(
            communication_health=health.communication_health if health else 0,
            automation_health=health.automation_health if health else 0,
            operational_health=health.operational_health if health else 0,
            growth_readiness=health.growth_readiness if health else 0
        ),
        consultation=ConsultationRecommendationSchema(
            recommended=consul.consultation_recommended if consul else False,
            confidence=consul.confidence if consul else 0.5,
            reasons=consul.reasons if consul else []
        ),
        structured_data=report.structured_data,
        narrative_summary=report.narrative_summary or "",
        narrative_evidence=schemas_mappings
    )
