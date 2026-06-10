import os
import asyncio
import logging
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select
from app.core.database import engine, Base, SessionLocal
from app.models.session import SessionORM
from app.models.profile import BusinessProfileORM
from app.models.event import SessionEventORM
from app.models.context import BusinessContextORM
from app.models.opportunity import (
    OpportunityEvaluationORM, OpportunityResultORM, OpportunityEvidenceORM,
    OpportunityTemplateORM, OpportunityGroupORM
)
from scripts.seed_questions import seed_data
from scripts.seed_opportunities import seed_opportunities
from scripts.seed_constraints import seed_constraints
from scripts.seed_applicability import seed_applicability
from scripts.seed_solutions import seed_solutions
from app.services.session import SessionService
from app.services.constraint_classifier import register_constraint_listeners
from app.services.applicability_engine import register_applicability_listeners
from app.services.solution_recommendation_engine import register_solution_listeners
from app.services.opportunity import register_opportunity_listeners
from app.services.event_store_listener import register_db_event_listener


# Configure Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tvira.verify_opportunities")

async def run_opportunities_verification():
    logger.info("Starting Tvira Business Opportunity Engine E2E Verification...")

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
    await seed_constraints()
    await seed_applicability()
    await seed_solutions()
    await seed_opportunities()
    logger.info("Questions, Constraints, Applicability, Solutions, and Opportunity catalogs seeded.")

    # 3. Register Event Listeners
    # Clear existing listeners first to avoid duplicate handler calls
    from app.services.event_bus import event_bus
    event_bus._listeners = {}
    event_bus._global_listeners = []

    register_db_event_listener()
    register_constraint_listeners()
    register_applicability_listeners()
    register_solution_listeners()
    register_opportunity_listeners()
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
        # which triggers database-driven opportunity calculations instantly
        logger.info("--- Step C: Completing discovery & triggering Opportunity Engine ---")
        session, profile = await service.complete_session(db, session.id)
        assert session.status.value == "PROFILE_GENERATED"
        logger.info("Discovery session sealed. Opportunity calculations finished.")

        # D. Assert persistence outcomes
        logger.info("--- Step D: Auditing Opportunity persisted outputs ---")
        
        # 1. Verify OpportunityEvaluation record
        eval_res = await db.execute(
            select(OpportunityEvaluationORM).where(OpportunityEvaluationORM.session_id == session.id)
        )
        eval_orm = eval_res.scalars().first()
        assert eval_orm is not None, "Opportunity evaluation ORM record was not found."
        assert eval_orm.engine_version == "1.0"
        assert eval_orm.ruleset_version == "2026.06.04"
        logger.info(f"Verified OpportunityEvaluation: ID {eval_orm.id}, Engine v{eval_orm.engine_version}")

        # 2. Verify OpportunityResults
        res_query = select(OpportunityResultORM).where(OpportunityResultORM.evaluation_id == eval_orm.id)
        res_results = await db.execute(res_query)
        results = list(res_results.scalars().all())
        
        result_map = {}
        for r in results:
            template = await db.get(OpportunityTemplateORM, r.template_id)
            result_map[template.code] = r
            
        logger.info(f"Generated opportunity results: {list(result_map.keys())}")
        
        # We expect AI_RECEPTIONIST and CRM_AUTOMATION
        assert "AI_RECEPTIONIST" in result_map
        assert "CRM_AUTOMATION" in result_map
        
        # 3. Deep audit AI_RECEPTIONIST details
        ai_rec = result_map["AI_RECEPTIONIST"]
        # Base impact = 70. Modifier 'Delayed followups' matched, adds +15. Clamped = 85.
        assert ai_rec.impact_score == 85, f"Expected impact score 85, got {ai_rec.impact_score}"
        # Base complexity = 30. No modifier rules matched complexity -> stays 30.
        assert ai_rec.complexity_score == 30, f"Expected complexity 30, got {ai_rec.complexity_score}"
        # Priority mapping: impact >= 80 and complexity <= 40 -> CRITICAL
        assert ai_rec.priority == "CRITICAL", f"Expected CRITICAL priority, got {ai_rec.priority}"
        
        # Reasoning list should contain reasons for high leads and WhatsApp channel
        assert len(ai_rec.reasoning) >= 2
        logger.info(f"AI Receptionist reasoning log: {ai_rec.reasoning}")

        # 4. Deep audit CRM_AUTOMATION details
        crm_aut = result_map["CRM_AUTOMATION"]
        # Base impact = 60. Modifier 'lead_volume_tier == HIGH' matched, adds +20. Clamped = 80.
        assert crm_aut.impact_score == 80, f"Expected CRM impact 80, got {crm_aut.impact_score}"
        assert crm_aut.complexity_score == 40
        assert crm_aut.priority == "CRITICAL"
        logger.info(f"CRM Automation reasoning log: {crm_aut.reasoning}")

        # 5. Verify Opportunity Evidence traces
        ev_res = await db.execute(select(OpportunityEvidenceORM).where(OpportunityEvidenceORM.result_id == ai_rec.id))
        evidences = list(ev_res.scalars().all())
        
        evidence_fields = [e.field for e in evidences]
        logger.info(f"AI Receptionist audit evidence traces saved: {evidence_fields}")
        
        assert "CUSTOMER_SUPPORT_severity" in evidence_fields
        assert "CUSTOMER_SUPPORT_confidence" in evidence_fields
        
        # Check specific values
        severity_evidence = [e for e in evidences if e.field == "CUSTOMER_SUPPORT_severity"][0]
        assert severity_evidence.value == "HIGH", f"Expected severity HIGH, got {severity_evidence.value}"
        assert severity_evidence.operator == "in"
        assert severity_evidence.rule_expression == "CUSTOMER_SUPPORT_severity in ['HIGH', 'CRITICAL']"

        # E. Verify event bus logs
        event_res = await db.execute(select(SessionEventORM).where(SessionEventORM.session_id == session.id))
        events = list(event_res.scalars().all())
        event_types = [e.event_type for e in events]
        logger.info(f"Audit event types logged: {event_types}")
        
        assert "OPPORTUNITIES_GENERATED" in event_types
        assert "OPPORTUNITY_EVALUATED" in event_types

    logger.info("=========================================")
    logger.info("SUCCESS: Tvira Business Opportunity Engine Verification Completed.")
    logger.info("=========================================")

if __name__ == "__main__":
    asyncio.run(run_opportunities_verification())
