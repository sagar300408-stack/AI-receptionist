import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import Dict, Any, List, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import SessionLocal
from app.core.exceptions import SessionNotFoundError
from app.domain.entities.profile import BusinessProfile
from app.domain.entities.report import BusinessReport, ReportVersion
from app.domain.events.base import TviraDomainEvent
from app.models.session import SessionORM
from app.models.profile import BusinessProfileORM
from app.models.context import BusinessContextORM
from app.models.opportunity import (
    OpportunityEvaluationORM, OpportunityResultORM, OpportunityEvidenceORM,
    OpportunityTemplateORM
)
from app.models.report import (
    ReportTemplateORM, BusinessReportORM, ReportVersionORM,
    ReportNarrativeEvidenceORM, QualificationResultORM,
    BusinessHealthAssessmentORM, ConsultationRecommendationORM
)
from app.services.event_bus import event_bus
from app.domain.policies.qualification import QualificationPolicy
from app.domain.policies.health import HealthAssessmentPolicy
from app.domain.policies.consultation import ConsultationPolicy
from app.services.report_builder import ReportBuilder
from app.services.grok_narrative import GrokNarrativeService

logger = logging.getLogger("tvira.report_service")

# Custom domain events for Segment 3
class ReportGeneratedEvent(TviraDomainEvent):
    def __init__(self, session_id: UUID, report_id: UUID, version: int):
        super().__init__(
            event_type="REPORT_GENERATED",
            session_id=session_id,
            payload={"report_id": str(report_id), "version": version}
        )

class LeadQualifiedEvent(TviraDomainEvent):
    def __init__(self, session_id: UUID, score: int, grade: str, routing_path: str):
        super().__init__(
            event_type="LEAD_QUALIFIED",
            session_id=session_id,
            payload={"score": score, "grade": grade, "routing_path": routing_path}
        )

class ConsultationRecommendedEvent(TviraDomainEvent):
    def __init__(self, session_id: UUID, recommended: bool, confidence: float):
        super().__init__(
            event_type="CONSULTATION_RECOMMENDED",
            session_id=session_id,
            payload={"recommended": recommended, "confidence": confidence}
        )

class ReportService:
    """Core coordinator governing Segment 3 report compilation, qualification audits, and historical archiving."""

    def __init__(self):
        self.grok_service = GrokNarrativeService()

    async def generate_or_regenerate_report(
        self, db: AsyncSession, session_id: UUID, force_regenerate: bool = False
    ) -> Tuple[BusinessReportORM, QualificationResultORM, BusinessHealthAssessmentORM, ConsultationRecommendationORM]:
        """Assembles report structured matrices, runs Grok narrative summaries, and saves historical versions."""
        logger.info(f"Generating business report for session {session_id}...")

        # 1. Fetch Session & Profile
        session_orm = await db.get(SessionORM, session_id)
        if not session_orm:
            raise SessionNotFoundError(str(session_id))

        p_query = select(BusinessProfileORM).where(BusinessProfileORM.session_id == session_id)
        p_result = await db.execute(p_query)
        profile_orm = p_result.scalars().first()
        
        profile_entity = BusinessProfile(
            id=profile_orm.id,
            session_id=profile_orm.session_id,
            industry=profile_orm.industry,
            business_type=profile_orm.business_type,
            team_size=profile_orm.team_size,
            monthly_leads=profile_orm.monthly_leads,
            monthly_customers=profile_orm.monthly_customers,
            business_stage=profile_orm.business_stage,
            communication_channels=profile_orm.communication_channels or [],
            pain_points=profile_orm.pain_points or [],
            goals=profile_orm.goals or [],
            profile_completion=profile_orm.profile_completion
        )

        # 2. Fetch Latest Opportunity Evaluation
        eval_query = select(OpportunityEvaluationORM).where(
            OpportunityEvaluationORM.session_id == session_id
        ).order_by(OpportunityEvaluationORM.evaluated_at.desc())
        eval_result = await db.execute(eval_query)
        evaluation = eval_result.scalars().first()
        if not evaluation:
            raise HTTPException(
                status_code=400,
                detail=f"No opportunity evaluations found for session {session_id}. Cannot compile report."
            )

        # Fetch opportunity results and evidence lists
        res_query = select(OpportunityResultORM).where(OpportunityResultORM.evaluation_id == evaluation.id)
        res_result = await db.execute(res_query)
        opportunity_results = list(res_result.scalars().all())

        ev_query = select(OpportunityEvidenceORM).where(
            OpportunityEvidenceORM.result_id.in_([r.id for r in opportunity_results])
        )
        ev_result = await db.execute(ev_query)
        evidence_list = list(ev_result.scalars().all())

        # Fetch Business Context Facts
        c_query = select(BusinessContextORM).where(BusinessContextORM.session_id == session_id)
        c_result = await db.execute(c_query)
        context_orm = c_result.scalars().first()
        context_facts = context_orm.facts if context_orm else {}

        # 3. Check if report already exists (deterministic caching check)
        r_query = select(BusinessReportORM).where(BusinessReportORM.session_id == session_id)
        r_result = await db.execute(r_query)
        existing_report = r_result.scalars().first()

        if existing_report and not force_regenerate:
            logger.info(f"Report already exists for session {session_id}, returning cached report.")
            # Load matching qualification, health, and consultation ORM
            q_res = await db.execute(select(QualificationResultORM).where(QualificationResultORM.session_id == session_id))
            h_res = await db.execute(select(BusinessHealthAssessmentORM).where(BusinessHealthAssessmentORM.session_id == session_id))
            c_res = await db.execute(select(ConsultationRecommendationORM).where(ConsultationRecommendationORM.session_id == session_id))
            return existing_report, q_res.scalars().first(), h_res.scalars().first(), c_res.scalars().first()

        opps_payload = []
        for r in opportunity_results:
            template = await db.get(OpportunityTemplateORM, r.template_id)
            opps_payload.append({
                "template_id": str(r.template_id),
                "template_code": template.code if template else "UNKNOWN",
                "priority": r.priority,
                "impact": r.impact_score,
                "complexity": r.complexity_score
            })
        qualification = QualificationPolicy.evaluate_qualification(profile_entity, opps_payload)
        
        # 5. Execute Business Health Engine
        health = HealthAssessmentPolicy.assess_health(profile_entity, opps_payload, context_facts)

        # 6. Execute Consultation Readiness Engine
        consultation = ConsultationPolicy.evaluate_booking(qualification, opps_payload)

        # 7. Execute structured report builder
        health_scores = {
            "communication_health": health.communication_health,
            "automation_health": health.automation_health,
            "operational_health": health.operational_health,
            "growth_readiness": health.growth_readiness
        }
        structured_data = ReportBuilder.build_structured_report(
            profile_entity, context_facts, opps_payload, health_scores
        )

        # 8. Resolve Report Layout Template
        t_query = select(ReportTemplateORM).where(
            ReportTemplateORM.industry == (profile_entity.industry or "Generic"),
            ReportTemplateORM.active == True
        )
        t_result = await db.execute(t_query)
        template = t_result.scalars().first()
        template_id = template.id if template else None

        # 9. Generate Narrative Summary (Grok / fallback)
        evidence_dicts = [
            {"id": e.id, "field": e.field, "value": e.value, "operator": e.operator, "rule_expression": e.rule_expression}
            for e in evidence_list
        ]
        narrative, evidence_mappings = await self.grok_service.generate_narrative(
            structured_data, profile_entity, evidence_dicts
        )

        # 10. Persist Report outcomes
        now = datetime.now(timezone.utc)
        
        # Upsert Qualification
        q_query = select(QualificationResultORM).where(QualificationResultORM.session_id == session_id)
        q_result = await db.execute(q_query)
        q_orm = q_result.scalars().first()
        if not q_orm:
            q_orm = QualificationResultORM(id=uuid4(), session_id=session_id, created_at=now)
            db.add(q_orm)
        q_orm.qualification_score = qualification.qualification_score
        q_orm.lead_grade = qualification.lead_grade.value
        q_orm.routing_path = qualification.routing_path.value
        q_orm.factors = qualification.factors
        q_orm.qualification_version = qualification.qualification_version
        
        # Upsert Health
        h_query = select(BusinessHealthAssessmentORM).where(BusinessHealthAssessmentORM.session_id == session_id)
        h_result = await db.execute(h_query)
        h_orm = h_result.scalars().first()
        if not h_orm:
            h_orm = BusinessHealthAssessmentORM(id=uuid4(), session_id=session_id, created_at=now)
            db.add(h_orm)
        h_orm.communication_health = health.communication_health
        h_orm.automation_health = health.automation_health
        h_orm.operational_health = health.operational_health
        h_orm.growth_readiness = health.growth_readiness
        h_orm.facts = health.facts
        h_orm.health_assessment_version = health.health_assessment_version

        # Upsert Booking
        c_query = select(ConsultationRecommendationORM).where(ConsultationRecommendationORM.session_id == session_id)
        c_result = await db.execute(c_query)
        c_orm = c_result.scalars().first()
        if not c_orm:
            c_orm = ConsultationRecommendationORM(id=uuid4(), session_id=session_id, created_at=now)
            db.add(c_orm)
        c_orm.consultation_recommended = consultation.consultation_recommended
        c_orm.confidence = consultation.confidence
        c_orm.reasons = consultation.reasons
        c_orm.consultation_version = consultation.consultation_version

        # Save or Update Report (with Version Archiving)
        report_version_num = 1
        
        if existing_report:
            # Increment and archive history before update
            v_num_query = select(func.max(ReportVersionORM.version_number)).where(
                ReportVersionORM.report_id == existing_report.id
            )
            v_num_result = await db.execute(v_num_query)
            max_v = v_num_result.scalar()
            report_version_num = (max_v or 1) + 1

            # Save snapshot to report_versions
            archive = ReportVersionORM(
                id=uuid4(),
                report_id=existing_report.id,
                version_number=report_version_num - 1, # Archive version number before incrementing
                structured_data=existing_report.structured_data,
                narrative_summary=existing_report.narrative_summary,
                engine_version=existing_report.engine_version,
                qualification_version=existing_report.qualification_version,
                health_assessment_version=existing_report.health_assessment_version,
                narrative_version=existing_report.narrative_version,
                created_at=existing_report.updated_at
            )
            db.add(archive)
            
            # Clean old evidence logs for this report
            del_query = select(ReportNarrativeEvidenceORM).where(ReportNarrativeEvidenceORM.report_id == existing_report.id)
            del_result = await db.execute(del_query)
            for old_ev in del_result.scalars().all():
                await db.delete(old_ev)

            # Update report ORM
            existing_report.structured_data = structured_data
            existing_report.narrative_summary = narrative
            existing_report.updated_at = now
            report_orm = existing_report
        else:
            # Create fresh report ORM
            report_orm = BusinessReportORM(
                id=uuid4(),
                session_id=session_id,
                evaluation_id=evaluation.id,
                template_id=template_id,
                structured_data=structured_data,
                narrative_summary=narrative,
                engine_version="1.0",
                qualification_version=qualification.qualification_version,
                health_assessment_version=health.health_assessment_version,
                narrative_version="1.0",
                created_at=now,
                updated_at=now
            )
            db.add(report_orm)

        await db.commit()
        await db.refresh(report_orm)

        # 11. Write Narrative-to-Evidence mappings
        for m in evidence_mappings:
            evidence_orm = ReportNarrativeEvidenceORM(
                id=uuid4(),
                report_id=report_orm.id,
                evidence_id=m["evidence_id"],
                paragraph_index=m["paragraph_index"],
                created_at=now
            )
            db.add(evidence_orm)

        await db.commit()

        logger.info(f"Business report saved: ID {report_orm.id}, version {report_version_num}.")

        # 12. Publish events
        await event_bus.publish(ReportGeneratedEvent(session_id, report_orm.id, report_version_num))
        await event_bus.publish(LeadQualifiedEvent(session_id, qualification.qualification_score, qualification.lead_grade.value, qualification.routing_path.value))
        await event_bus.publish(ConsultationRecommendedEvent(session_id, consultation.consultation_recommended, consultation.confidence))

        return report_orm, q_orm, h_orm, c_orm

# Event listener mapping OPPORTUNITIES_GENERATED to Segment 3
async def on_opportunities_generated_listener(event: TviraDomainEvent):
    """Subscribed handler intercepting OPPORTUNITIES_GENERATED to compile reports automatically."""
    if event.event_type != "OPPORTUNITIES_GENERATED":
        return

    logger.info(f"Event subscriber intercepting OPPORTUNITIES_GENERATED event for session: {event.session_id}")
    
    async with SessionLocal() as db:
        try:
            service = ReportService()
            await service.generate_or_regenerate_report(db, event.session_id)
        except Exception as e:
            logger.error(f"Async report compilation failed for session {event.session_id}: {e}")

def register_report_listeners():
    """Binds Segment 3 subscribers to the domain Event Bus."""
    event_bus.subscribe("OPPORTUNITIES_GENERATED", on_opportunities_generated_listener)
