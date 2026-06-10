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
from app.models.applicability import AIApplicabilityORM, ReviewQueueORM, ApplicabilityRuleORM
from app.models.opportunity import OpportunityEvaluationORM, OpportunityResultORM, OpportunityTemplateORM
from scripts.seed_questions import seed_data
from scripts.seed_constraints import seed_constraints
from scripts.seed_applicability import seed_applicability
from scripts.seed_solutions import seed_solutions
from scripts.seed_opportunities import seed_opportunities
from app.services.session import SessionService
from app.services.constraint_classifier import register_constraint_listeners
from app.services.applicability_engine import register_applicability_listeners
from app.services.solution_recommendation_engine import register_solution_listeners
from app.services.opportunity import register_opportunity_listeners
from app.services.event_store_listener import register_db_event_listener
from app.main import app

# Configure Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tvira.verify_applicability")

async def run_applicability_verification():
    logger.info("Starting Tvira Business AI Applicability Engine E2E Verification...")

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
    logger.info("Questions, Constraints, Applicability rules, Solutions catalog, and Opportunities catalogs seeded.")

    # 3. Register Event Listeners (Clear first to avoid duplicate handler calls during publish)
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

    # --- SESSION 1: Coaching Institute (Matches Rules & Highly Applicable) ---
    async with SessionLocal() as db:
        logger.info("--- Step A: Creating Session 1 ---")
        session1, profile1 = await service.create_session(db)

        logger.info("--- Step B: Answering discovery questions for Session 1 ---")
        # business_type -> Coaching Institute
        session1, profile1, _ = await service.respond_to_question(
            db, session1.id, "business_type", "Coaching Institute"
        )
        # team_size -> 12
        session1, profile1, _ = await service.respond_to_question(
            db, session1.id, "team_size", "We have a team of 12 people"
        )
        # monthly_leads -> 600
        session1, profile1, _ = await service.respond_to_question(
            db, session1.id, "monthly_leads", "About 600 monthly inquiries"
        )
        # monthly_customers -> 150
        session1, profile1, _ = await service.respond_to_question(
            db, session1.id, "monthly_customers", "We handle 150 student enrollments each month"
        )
        # coaching_inquiries -> tracked on spreadsheets
        session1, profile1, _ = await service.respond_to_question(
            db, session1.id, "coaching_inquiries", "Admissions are tracked on spreadsheets"
        )
        # communication_channels -> WhatsApp and Email
        session1, profile1, _ = await service.respond_to_question(
            db, session1.id, "communication_channels", "WhatsApp and Email"
        )
        # pain_points -> Delayed followups
        session1, profile1, _ = await service.respond_to_question(
            db, session1.id, "pain_points", "Delayed followups"
        )
        # goals -> Automate counselor workflow
        session1, profile1, _ = await service.respond_to_question(
            db, session1.id, "goals", "Automate counselor workflow"
        )
        logger.info("Questionnaire walkthrough completed for Session 1.")

        logger.info("--- Step C: Completing discovery & triggering cascade engines ---")
        session1, profile1 = await service.complete_session(db, session1.id)
        assert session1.status.value == "PROFILE_GENERATED"
        logger.info("Discovery session sealed. Cascaded calculations finished.")

    # Allow async tasks to fully execute and settle database writes
    await asyncio.sleep(0.5)

    # --- Step D: Assert Persisted Applicability and Decoupled Opportunities ---
    logger.info("--- Step D: Auditing Session 1 persisted outputs ---")
    async with SessionLocal() as db:
        # 1. Verify applicability results
        app_res = await db.execute(select(AIApplicabilityORM).where(AIApplicabilityORM.session_id == session1.id))
        applicabilities = list(app_res.scalars().all())
        
        # We expect CUSTOMER_SUPPORT, LEAD_QUALIFICATION, SCHEDULING, OPERATIONS results
        # We mapped constraints to applicability rules. Let's retrieve constraint list to match IDs.
        const_res = await db.execute(select(ConstraintORM).where(ConstraintORM.session_id == session1.id))
        constraints = list(const_res.scalars().all())
        constraint_map = {c.id: c.category for c in constraints}

        app_map = {}
        for a in applicabilities:
            c_cat = constraint_map.get(a.constraint_id)
            app_map[c_cat] = a

        logger.info(f"Evaluated applicability categories: {list(app_map.keys())}")
        assert "CUSTOMER_SUPPORT" in app_map
        assert "LEAD_QUALIFICATION" in app_map
        assert "SCHEDULING" in app_map
        assert "OPERATIONS" in app_map

        # Verify CUSTOMER_SUPPORT applicability details
        support_a = app_map["CUSTOMER_SUPPORT"]
        assert support_a.category == "HIGHLY_APPLICABLE"
        assert support_a.applicability_score == 95
        assert support_a.confidence == 92
        assert "AI_RECEPTIONIST" in support_a.recommended_solution_types
        assert "CUSTOMER_SUPPORT_AUTOMATION" in support_a.recommended_solution_types
        assert support_a.rule_version == "1.0"
        
        # Verify structured evidence items inside the applicability result
        logger.info(f"Customer Support applicability evidence: {support_a.evidence}")
        assert len(support_a.evidence) > 0
        for ev in support_a.evidence:
            assert "source" in ev
            assert "value" in ev
            assert "reason" in ev

        # 2. Verify Opportunities evaluated based on applicability states in context_facts
        eval_res = await db.execute(select(OpportunityEvaluationORM).where(OpportunityEvaluationORM.session_id == session1.id))
        eval_orm = eval_res.scalars().first()
        assert eval_orm is not None, "Opportunity evaluation ORM record not found."
        
        res_query = select(OpportunityResultORM).where(OpportunityResultORM.evaluation_id == eval_orm.id)
        res_results = await db.execute(res_query)
        opp_results = list(res_results.scalars().all())
        
        opp_codes = []
        for r in opp_results:
            template = await db.get(OpportunityTemplateORM, r.template_id)
            opp_codes.append(template.code)
            
        logger.info(f"Evaluated opportunities for Session 1: {opp_codes}")
        assert "AI_RECEPTIONIST" in opp_codes, "AI_RECEPTIONIST opportunity should be eligible"
        assert "CRM_AUTOMATION" in opp_codes, "CRM_AUTOMATION opportunity should be eligible"
        assert "APPOINTMENT_SCHEDULING" in opp_codes, "APPOINTMENT_SCHEDULING opportunity should be eligible"

    # --- Step E: Verify API Layer Contracts ---
    logger.info("--- Step E: Verifying API layer contracts ---")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Test GET /api/v1/sessions/{session_id}/applicability
        response = await client.get(f"/api/v1/sessions/{session1.id}/applicability")
        assert response.status_code == 200, f"GET applicability failed: {response.text}"
        data = response.json()
        
        assert data["session_id"] == str(session1.id)
        assert len(data["results"]) > 0
        logger.info(f"Verified GET applicability API response schema: {data['results'][0]}")

        # Test POST /api/v1/sessions/{session_id}/applicability/recalculate
        regen_response = await client.post(f"/api/v1/sessions/{session1.id}/applicability/recalculate")
        assert regen_response.status_code == 200, f"POST recalculate failed: {regen_response.text}"
        regen_data = regen_response.json()
        assert len(regen_data["results"]) > 0
        logger.info("Verified POST Recalculate applicability endpoint completed successfully.")

        # Test GET /api/v1/sessions/{session_id}/review-queue
        review_response = await client.get(f"/api/v1/sessions/{session1.id}/review-queue")
        assert review_response.status_code == 200, f"GET review queue failed: {review_response.text}"
        review_data = review_response.json()
        # Should be empty list or low priority entries only
        logger.info(f"Verified GET review-queue response: {review_data}")

    # --- SESSION 2: Unknown constraint & conflicting conversion metrics to trigger Manual Review Queue ---
    async with SessionLocal() as db:
        logger.info("--- Step F: Creating Session 2 (Conflicting/Unknown signals) ---")
        session2, profile2 = await service.create_session(db)

        # We set monthly_leads = 500, monthly_customers = 0 (conflicting signals)
        # This will trigger UNKNOWN constraint category and fallbacks
        session2, profile2, _ = await service.respond_to_question(
            db, session2.id, "business_type", "Coaching Institute"
        )
        session2, profile2, _ = await service.respond_to_question(
            db, session2.id, "team_size", "We have a team of 1"
        )
        session2, profile2, _ = await service.respond_to_question(
            db, session2.id, "monthly_leads", "About 500 monthly inquiries"
        )
        session2, profile2, _ = await service.respond_to_question(
            db, session2.id, "monthly_customers", "We handle 0 paying customers"
        )
        session2, profile2, _ = await service.respond_to_question(
            db, session2.id, "coaching_inquiries", "None"
        )
        session2, profile2, _ = await service.respond_to_question(
            db, session2.id, "communication_channels", "Email only"
        )
        session2, profile2, _ = await service.respond_to_question(
            db, session2.id, "pain_points", "None"
        )
        session2, profile2, _ = await service.respond_to_question(
            db, session2.id, "goals", "Growth"
        )
        
        logger.info("--- Step G: Completing Session 2 and checking Review Queue triggers ---")
        session2, profile2 = await service.complete_session(db, session2.id)

    # Allow async tasks to settle
    await asyncio.sleep(0.5)

    async with SessionLocal() as db:
        # 1. Verify review queue database items
        q_res = await db.execute(select(ReviewQueueORM).where(ReviewQueueORM.session_id == session2.id))
        queue_items = list(q_res.scalars().all())
        
        reasons = [q.reason for q in queue_items]
        priorities = [q.priority for q in queue_items]
        logger.info(f"Review queue items for Session 2: Reasons: {reasons}, Priorities: {priorities}")
        
        assert len(queue_items) > 0, "Expected at least one manual review queue entry for Session 2."
        # We expect a HIGH priority entry due to UNKNOWN constraint category and score < 40 / version N/A
        assert "HIGH" in priorities, "Expected HIGH priority manual review item"
        
        # Verify specific reasons
        unknown_reasons = [r for r in reasons if "UNKNOWN" in r or "No active AI applicability rules matched" in r or "Low AI applicability score" in r]
        assert len(unknown_reasons) > 0, "Expected triage reasons for UNKNOWN constraint fallback"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Test HTTP GET review queue API
        api_review_response = await client.get(f"/api/v1/sessions/{session2.id}/review-queue")
        assert api_review_response.status_code == 200, f"GET review queue failed: {api_review_response.text}"
        api_review_data = api_review_response.json()
        assert len(api_review_data) > 0
        logger.info(f"Verified GET /review-queue response structure: {api_review_data[0]}")

    logger.info("=========================================")
    logger.info("SUCCESS: Tvira Business AI Applicability Engine E2E Verification Completed.")
    logger.info("=========================================")

if __name__ == "__main__":
    asyncio.run(run_applicability_verification())
