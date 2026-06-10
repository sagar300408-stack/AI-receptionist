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
from app.models.constraint import ConstraintORM
from app.models.applicability import AIApplicabilityORM
from app.models.solution import SolutionCatalogORM, RecommendedSolutionORM
from app.models.opportunity import OpportunityEvaluationORM, OpportunityResultORM, OpportunityTemplateORM
from app.models.report import BusinessReportORM
from scripts.seed_questions import seed_data
from scripts.seed_constraints import seed_constraints
from scripts.seed_applicability import seed_applicability
from scripts.seed_solutions import seed_solutions
from scripts.seed_opportunities import seed_opportunities
from scripts.seed_reports import seed_reports
from app.services.session import SessionService
from app.services.constraint_classifier import register_constraint_listeners
from app.services.applicability_engine import register_applicability_listeners
from app.services.solution_recommendation_engine import register_solution_listeners
from app.services.opportunity import register_opportunity_listeners
from app.services.report_service import register_report_listeners
from app.services.event_store_listener import register_db_event_listener
from app.main import app

# Configure Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tvira.verify_solutions")

async def run_solutions_verification():
    logger.info("Starting Tvira Business Solution Recommendation Engine E2E Verification...")

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
    await seed_reports()
    logger.info("Catalogs: Questions, Constraints, Applicability rules, Solutions catalog, Opportunities templates, and Report templates seeded.")

    # 3. Register Event Listeners (Clear first to avoid duplicate handler calls)
    from app.services.event_bus import event_bus
    event_bus._listeners = {}
    event_bus._global_listeners = []

    register_db_event_listener()
    register_constraint_listeners()
    register_applicability_listeners()
    register_solution_listeners()
    register_opportunity_listeners()
    register_report_listeners()
    logger.info("Domain Event Bus listeners registered.")

    service = SessionService()

    # --- SESSION: Coaching Institute (Matches Rules & Solutions) ---
    async with SessionLocal() as db:
        logger.info("--- Step A: Creating Session ---")
        session, profile = await service.create_session(db)

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
        # goals -> Automate counselor workflow
        session, profile, _ = await service.respond_to_question(
            db, session.id, "goals", "Automate counselor workflow"
        )
        logger.info("Questionnaire walkthrough completed.")

        logger.info("--- Step C: Completing discovery & triggering cascade engines ---")
        session, profile = await service.complete_session(db, session.id)
        assert session.status.value == "PROFILE_GENERATED"
        logger.info("Discovery session sealed. Cascaded calculations finished.")

    # Allow async tasks to fully execute and settle database writes
    await asyncio.sleep(0.5)

    # --- Step D: Assert Persisted Solutions and Decoupled Opportunities ---
    logger.info("--- Step D: Auditing Session persisted outputs ---")
    async with SessionLocal() as db:
        # 1. Verify solution recommendations
        sol_res = await db.execute(select(RecommendedSolutionORM).where(RecommendedSolutionORM.session_id == session.id))
        solutions = list(sol_res.scalars().all())
        
        logger.info(f"Persisted solutions: {[s.solution_type for s in solutions]}")
        assert len(solutions) > 0, "No recommended solutions found."

        # Find specific solution type e.g. AI_RECEPTIONIST
        sol_types = [s.solution_type for s in solutions]
        assert "AI_RECEPTIONIST" in sol_types
        assert "CRM_AUTOMATION" in sol_types
        assert "APPOINTMENT_SCHEDULING" in sol_types

        # Verify priority score generation details for AI_RECEPTIONIST
        ai_rec_sol = [s for s in solutions if s.solution_type == "AI_RECEPTIONIST"][0]
        # priority_score = round(applicability_score * 0.4 + impact_score * 0.4 + confidence * 0.2)
        # From Constraint: impact_score = 70 (Delayed followups modifier can add some, or base impact), confidence = 90
        # From Applicability: score = 95
        # Let's verify it is generated as a valid integer and not None
        assert ai_rec_sol.priority_score > 0
        logger.info(f"AI Receptionist priority score: {ai_rec_sol.priority_score}")

        # Check structured evidence is stored in JSON list format
        assert len(ai_rec_sol.evidence) > 0
        for ev in ai_rec_sol.evidence:
            assert "source" in ev
            assert "value" in ev
            assert "reason" in ev
        logger.info(f"Structured evidence verified: {ai_rec_sol.evidence}")

        # 2. Verify Opportunities evaluated based on recommended solution states in context_facts
        eval_res = await db.execute(select(OpportunityEvaluationORM).where(OpportunityEvaluationORM.session_id == session.id))
        eval_orm = eval_res.scalars().first()
        assert eval_orm is not None, "Opportunity evaluation ORM record not found."
        
        res_query = select(OpportunityResultORM).where(OpportunityResultORM.evaluation_id == eval_orm.id)
        res_results = await db.execute(res_query)
        opp_results = list(res_results.scalars().all())
        
        opp_codes = []
        for r in opp_results:
            template = await db.get(OpportunityTemplateORM, r.template_id)
            opp_codes.append(template.code)
            
        logger.info(f"Evaluated opportunities: {opp_codes}")
        assert "AI_RECEPTIONIST" in opp_codes, "AI_RECEPTIONIST opportunity should be eligible based on recommended solutions."
        assert "CRM_AUTOMATION" in opp_codes, "CRM_AUTOMATION opportunity should be eligible."
        assert "APPOINTMENT_SCHEDULING" in opp_codes, "APPOINTMENT_SCHEDULING opportunity should be eligible."

        # 3. Verify that reports are generated successfully
        rep_res = await db.execute(select(BusinessReportORM).where(BusinessReportORM.session_id == session.id))
        report = rep_res.scalars().first()
        assert report is not None, "Report should still be generated successfully."
        logger.info(f"Business Report verified: ID={report.id}, Lead Grade={report.lead_grade}")

    # --- Step E: Verify API Layer Contracts ---
    logger.info("--- Step E: Verifying API layer contracts ---")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Test GET /api/v1/sessions/{session_id}/solutions
        response = await client.get(f"/api/v1/sessions/{session.id}/solutions")
        assert response.status_code == 200, f"GET solutions failed: {response.text}"
        data = response.json()
        
        assert data["session_id"] == str(session.id)
        assert len(data["results"]) > 0
        logger.info(f"Verified GET solutions API response schema: {data['results'][0]}")

        # Test POST /api/v1/sessions/{session_id}/solutions/recalculate
        regen_response = await client.post(f"/api/v1/sessions/{session.id}/solutions/recalculate")
        assert regen_response.status_code == 200, f"POST recalculate failed: {regen_response.text}"
        regen_data = regen_response.json()
        assert len(regen_data["results"]) > 0
        logger.info("Verified POST Recalculate solutions endpoint completed successfully.")

    # --- Step F: Verify Event logs in Event Store ---
    async with SessionLocal() as db:
        event_res = await db.execute(select(SessionEventORM).where(SessionEventORM.session_id == session.id))
        events = list(event_res.scalars().all())
        event_types = [e.event_type for e in events]
        logger.info(f"Audit event types logged: {event_types}")
        
        assert "SOLUTIONS_RECOMMENDED" in event_types, "Event bus did not log SOLUTIONS_RECOMMENDED event."
        assert "OPPORTUNITIES_GENERATED" in event_types, "Opportunity Engine failed to cascade after Solutions."

    logger.info("=========================================")
    logger.info("SUCCESS: Tvira Business Solution Recommendation Engine E2E Verification Completed.")
    logger.info("=========================================")

if __name__ == "__main__":
    asyncio.run(run_solutions_verification())
