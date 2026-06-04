import os
import asyncio
import logging
from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlalchemy import select
from httpx import AsyncClient, ASGITransport

from app.core.database import engine, Base, SessionLocal
from app.models.session import SessionORM
from app.models.profile import BusinessProfileORM
from app.models.event import SessionEventORM
from app.models.context import BusinessContextORM
from app.models.opportunity import (
    OpportunityEvaluationORM, OpportunityResultORM, OpportunityEvidenceORM,
    OpportunityTemplateORM, OpportunityGroupORM, OpportunityRuleORM
)
from app.models.report import (
    BusinessReportORM, ReportVersionORM, ReportNarrativeEvidenceORM,
    QualificationResultORM, BusinessHealthAssessmentORM,
    ConsultationRecommendationORM, ReportTemplateORM
)
from scripts.seed_questions import seed_data
from scripts.seed_opportunities import seed_opportunities
from scripts.seed_reports import seed_reports
from app.services.session import SessionService
from app.services.report_service import ReportService, register_report_listeners
from app.services.opportunity import register_opportunity_listeners
from app.services.event_store_listener import register_db_event_listener
from app.main import app

# Configure Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tvira.verify_report")

async def seed_strategic_project_template(db):
    res = await db.execute(select(OpportunityGroupORM).where(OpportunityGroupORM.name == "Operations Automation"))
    group = res.scalars().first()
    group_id = group.id if group else None

    now = datetime.now(timezone.utc)
    t_code = "STRATEGIC_TEST"
    
    res_t = await db.execute(select(OpportunityTemplateORM).where(
        OpportunityTemplateORM.code == t_code
    ))
    existing = res_t.scalars().first()
    if not existing:
        template = OpportunityTemplateORM(
            id=uuid4(),
            group_id=group_id,
            code=t_code,
            name="Strategic Test Project",
            version="v1",
            description="A high impact, high complexity strategic project for verification purposes.",
            base_impact=70.0,
            base_complexity=50.0,
            active=True,
            created_at=now,
            updated_at=now
        )
        db.add(template)
        await db.commit()
        await db.refresh(template)
        
        # Add eligibility rule
        rule = OpportunityRuleORM(
            id=uuid4(),
            template_id=template.id,
            rule_type="ELIGIBILITY",
            conditions={"field": "monthly_leads", "operator": "gt", "value": 100},
            modifier_value=None,
            explanation_template=None,
            active=True,
            created_at=now
        )
        db.add(rule)
        
        # Add reasoning rule to generate evidence
        rule_reason = OpportunityRuleORM(
            id=uuid4(),
            template_id=template.id,
            rule_type="REASONING",
            conditions={"field": "monthly_leads", "operator": "gt", "value": 300},
            modifier_value=None,
            explanation_template="High volume of monthly leads ({monthly_leads}) requires complex systems integration.",
            active=True,
            created_at=now
        )
        db.add(rule_reason)
        await db.commit()
        logger.info("Seeded strategic project template for verification.")

async def run_report_verification():
    logger.info("Starting Tvira Business Report & Qualification Engine E2E Verification...")

    # 1. Clean database state if SQLite is used
    db_file = "./tvira_business.db"
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
            logger.info("Removed existing test database for clean run.")
        except Exception as e:
            logger.warning(f"Could not remove database file: {e}")

    # 2. Run Seed Scripts
    await seed_data()
    await seed_opportunities()
    await seed_reports()
    logger.info("Questions, Opportunity catalogs, and Report templates seeded.")

    # Seed the strategic project template to ensure we have a strategic project quadrant item
    async with SessionLocal() as db:
        await seed_strategic_project_template(db)

    # 3. Register Event Listeners (Clear first to avoid duplicate handler calls during publish)
    from app.services.event_bus import event_bus
    event_bus._listeners = {}
    event_bus._global_listeners = []

    register_db_event_listener()
    register_opportunity_listeners()
    register_report_listeners()
    logger.info("Domain Event Bus listeners registered.")

    service = SessionService()

    async with SessionLocal() as db:
        # A. Start Session
        logger.info("--- Step A: Creating Session ---")
        session, profile = await service.create_session(db)
        
        # B. Answer questions in sequence
        logger.info("--- Step B: Answering discovery questions ---")
        
        # business_type -> Coaching Institute
        session, profile, _ = await service.respond_to_question(
            db, session.id, "business_type", "Coaching Institute"
        )
        # team_size -> 12
        session, profile, _ = await service.respond_to_question(
            db, session.id, "team_size", "We have a team of 12 people"
        )
        # monthly_leads -> 600
        session, profile, _ = await service.respond_to_question(
            db, session.id, "monthly_leads", "About 600 monthly inquiries"
        )
        # monthly_customers -> 150
        session, profile, _ = await service.respond_to_question(
            db, session.id, "monthly_customers", "We handle 150 student enrollments each month"
        )
        # coaching_inquiries -> tracked on spreadsheets
        session, profile, _ = await service.respond_to_question(
            db, session.id, "coaching_inquiries", "Admissions are tracked on spreadsheets"
        )
        # communication_channels -> WhatsApp and Email
        session, profile, _ = await service.respond_to_question(
            db, session.id, "communication_channels", "WhatsApp and Email"
        )
        # pain_points -> Delayed followups
        session, profile, _ = await service.respond_to_question(
            db, session.id, "pain_points", "Delayed followups"
        )
        # goals -> Automate
        session, profile, _ = await service.respond_to_question(
            db, session.id, "goals", "Automate counselor workflow"
        )

        logger.info("Questionnaire walkthrough completed.")

        # C. Complete discovery session -> This publishes DISCOVERY_COMPLETED event
        # which triggers database-driven opportunity calculations, followed by report generation automatically
        logger.info("--- Step C: Completing discovery & triggering cascade engines ---")
        session, profile = await service.complete_session(db, session.id)
        assert session.status.value == "PROFILE_GENERATED"
        logger.info("Discovery session sealed. Cascaded calculations finished.")

    # Allow async tasks to fully execute and settle database writes
    await asyncio.sleep(0.5)

    # D. Assert persistence outcomes
    logger.info("--- Step D: Auditing Segment 3 persisted outputs ---")
    
    async with SessionLocal() as db:
        # 1. Verify qualification_results records the routing path ENTERPRISE
        q_res = await db.execute(select(QualificationResultORM).where(QualificationResultORM.session_id == session.id))
        qual = q_res.scalars().first()
        assert qual is not None, "QualificationResultORM record not found."
        assert qual.lead_grade == "HOT", f"Expected grade HOT, got {qual.lead_grade}"
        assert qual.routing_path == "ENTERPRISE", f"Expected ENTERPRISE routing path, got {qual.routing_path}"
        logger.info(f"Verified Qualification: score {qual.qualification_score}, routing path {qual.routing_path}")

        # 2. Verify business_reports exists and holds the priority matrix containing "Quick Wins" and "Strategic Projects"
        r_res = await db.execute(select(BusinessReportORM).where(BusinessReportORM.session_id == session.id))
        report = r_res.scalars().first()
        assert report is not None, "BusinessReportORM record not found."
        
        priority_matrix = report.structured_data.get("priority_matrix", {})
        quick_wins = priority_matrix.get("quick_wins", [])
        strategic_projects = priority_matrix.get("strategic_projects", [])
        
        logger.info(f"Priority matrix items: Quick Wins: {quick_wins}, Strategic Projects: {strategic_projects}")
        
        assert len(quick_wins) > 0, "Expected at least one Quick Win opportunity."
        assert len(strategic_projects) > 0, "Expected at least one Strategic Project opportunity."
        
        # Verify specific items
        quick_win_codes = [qw["code"] for qw in quick_wins]
        assert "AI_RECEPTIONIST" in quick_win_codes, "AI_RECEPTIONIST should be a Quick Win."
        
        strategic_codes = [sp["code"] for sp in strategic_projects]
        assert "STRATEGIC_TEST" in strategic_codes, "STRATEGIC_TEST should be a Strategic Project."
        logger.info("Verified Executive Priority Matrix quadrants successfully.")

        # 3. Verify report_narrative_evidence mapping tables contain links between paragraphs and active evidence ids
        ne_query = select(ReportNarrativeEvidenceORM).where(ReportNarrativeEvidenceORM.report_id == report.id)
        ne_results = await db.execute(ne_query)
        ne_records = list(ne_results.scalars().all())
        assert len(ne_records) > 0, "No narrative evidence mapping records found."
        for rec in ne_records:
            assert rec.paragraph_index in [0, 1], f"Unexpected paragraph index {rec.paragraph_index}"
            # Check corresponding evidence
            ev = await db.get(OpportunityEvidenceORM, rec.evidence_id)
            assert ev is not None, f"Evidence ID {rec.evidence_id} not found in database."
            assert ev.field in ["monthly_leads", "communication_channels"], f"Unexpected evidence field: {ev.field}"
            logger.info(f"Verified Evidence Link: Paragraph {rec.paragraph_index} maps to evidence field '{ev.field}'")

    # E. Verify API Contract via httpx.AsyncClient
    logger.info("--- Step E: Verifying API layer contracts ---")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Test GET /api/v1/sessions/{session_id}/report
        response = await client.get(f"/api/v1/sessions/{session.id}/report")
        assert response.status_code == 200, f"GET report failed: {response.text}"
        data = response.json()
        
        assert data["report_id"] is not None
        assert data["version"] == 1
        assert data["template_name"] == "Coaching Report Template"
        assert data["qualification"]["routing_path"] == "ENTERPRISE"
        assert len(data["structured_data"]["priority_matrix"]["quick_wins"]) > 0
        assert len(data["structured_data"]["priority_matrix"]["strategic_projects"]) > 0
        assert data["narrative_summary"] != ""
        assert len(data["narrative_evidence"]) > 0
        logger.info(f"Verified GET Report response structure. Narrative summary prefix: '{data['narrative_summary'][:60]}...'")

        # 2. Test POST /api/v1/sessions/{session_id}/report/regenerate
        regen_response = await client.post(f"/api/v1/sessions/{session.id}/report/regenerate")
        assert regen_response.status_code == 200, f"POST regenerate failed: {regen_response.text}"
        regen_data = regen_response.json()
        assert regen_data["version"] == 2
        logger.info("Verified POST Regenerate report version increment.")

    # F. Verify report_versions logs incremental snapshots with historical values preserved
    logger.info("--- Step F: Verifying Report Versioning table ---")
    async with SessionLocal() as db:
        v_res = await db.execute(select(ReportVersionORM).where(ReportVersionORM.report_id == report.id))
        versions = list(v_res.scalars().all())
        assert len(versions) == 1, f"Expected exactly 1 archived report version, got {len(versions)}"
        v1 = versions[0]
        assert v1.version_number == 1, f"Expected archived version number 1, got {v1.version_number}"
        assert v1.narrative_summary == report.narrative_summary, "Archived narrative summary does not match original."
        logger.info(f"Verified report version history record for report ID {report.id} saved correctly.")

    logger.info("=========================================")
    logger.info("SUCCESS: Tvira Business Segment 3 (Report & Qualification Engine) Verification Completed.")
    logger.info("=========================================")

if __name__ == "__main__":
    asyncio.run(run_report_verification())
