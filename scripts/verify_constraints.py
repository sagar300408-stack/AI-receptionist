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
from app.models.constraint import ConstraintORM, ConstraintRuleORM
from app.models.opportunity import OpportunityEvaluationORM, OpportunityResultORM, OpportunityTemplateORM
from scripts.seed_questions import seed_data
from scripts.seed_opportunities import seed_opportunities
from scripts.seed_constraints import seed_constraints
from scripts.seed_applicability import seed_applicability
from scripts.seed_solutions import seed_solutions
from app.services.session import SessionService
from app.services.constraint_classifier import register_constraint_listeners
from app.services.applicability_engine import register_applicability_listeners
from app.services.solution_recommendation_engine import register_solution_listeners
from app.services.founder_review_engine import register_founder_review_listeners
from app.services.opportunity import register_opportunity_listeners
from app.services.event_store_listener import register_db_event_listener
from app.main import app

# Configure Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tvira.verify_constraints")

async def run_constraints_verification():
    logger.info("Starting Tvira Business Constraint Classification Engine E2E Verification...")

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
    logger.info("Questions, Constraint rules, and Opportunity catalogs seeded.")

    # 3. Register Event Listeners (Clear first to avoid duplicate handler calls during publish)
    from app.services.event_bus import event_bus
    event_bus._listeners = {}
    event_bus._global_listeners = []

    register_db_event_listener()
    register_constraint_listeners()
    register_applicability_listeners()
    register_solution_listeners()
    register_founder_review_listeners()
    register_opportunity_listeners()
    logger.info("Domain Event Bus listeners registered.")

    service = SessionService()

    # --- SESSION 1: Coaching Institute (Matches Rules) ---
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

        logger.info("--- Step C: Completing discovery & triggering Constraint Engine ---")
        session1, profile1 = await service.complete_session(db, session1.id)
        assert session1.status.value == "PROFILE_GENERATED"
        logger.info("Discovery session sealed. Cascaded calculations finished.")

        # Approve review session to trigger opportunity evaluations
        from app.services.founder_review_engine import FounderReviewEngine
        review_engine = FounderReviewEngine()
        await review_engine.approve_all_reviews_for_session(db, session1.id)

    # Allow async tasks to fully execute and settle database writes
    await asyncio.sleep(0.5)

    # --- Step D: Assert Persisted Constraints and Opportunities ---
    logger.info("--- Step D: Auditing Session 1 persisted outputs ---")
    async with SessionLocal() as db:
        # 1. Verify constraints
        c_res = await db.execute(select(ConstraintORM).where(ConstraintORM.session_id == session1.id))
        constraints = list(c_res.scalars().all())
        
        categories = [c.category for c in constraints]
        logger.info(f"Identified constraints for Session 1: {categories}")
        
        # We expect CUSTOMER_SUPPORT, LEAD_QUALIFICATION, SCHEDULING, OPERATIONS
        assert "CUSTOMER_SUPPORT" in categories, "Expected CUSTOMER_SUPPORT constraint"
        assert "LEAD_QUALIFICATION" in categories, "Expected LEAD_QUALIFICATION constraint"
        assert "SCHEDULING" in categories, "Expected SCHEDULING constraint"
        assert "OPERATIONS" in categories, "Expected OPERATIONS constraint"

        # Check a specific constraint details
        support_c = [c for c in constraints if c.category == "CUSTOMER_SUPPORT"][0]
        assert support_c.severity == "HIGH", f"Expected CUSTOMER_SUPPORT severity HIGH, got {support_c.severity}"
        assert support_c.impact_score == 85, f"Expected impact_score 85, got {support_c.impact_score}"
        assert "pain_points" in support_c.origin, "Expected 'pain_points' in origin"
        
        # Audit structured evidence schema
        assert len(support_c.evidence) > 0
        for e in support_c.evidence:
            assert "source" in e
            assert "value" in e
            assert "reason" in e
            logger.info(f"Constraint evidence: {e}")

        # 2. Verify Opportunities evaluated via Constraint states in context_facts
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
        # Test GET /api/v1/sessions/{session_id}/constraints
        response = await client.get(f"/api/v1/sessions/{session1.id}/constraints")
        assert response.status_code == 200, f"GET constraints failed: {response.text}"
        data = response.json()
        
        assert data["session_id"] == str(session1.id)
        assert len(data["constraints"]) > 0
        logger.info(f"Verified GET constraints API response schema: {data['constraints'][0]}")

        # Test POST /api/v1/sessions/{session_id}/constraints/recalculate
        regen_response = await client.post(f"/api/v1/sessions/{session1.id}/constraints/recalculate")
        assert regen_response.status_code == 200, f"POST recalculate failed: {regen_response.text}"
        regen_data = regen_response.json()
        assert len(regen_data["constraints"]) > 0
        logger.info("Verified POST Recalculate constraints endpoint completed successfully.")

    # --- SESSION 2: Conflicting metrics to trigger UNKNOWN constraint policy ---
    async with SessionLocal() as db:
        logger.info("--- Step F: Creating Session 2 (Conflicting Signals) ---")
        session2, profile2 = await service.create_session(db)

        # We set monthly_leads = 500, monthly_customers = 0 (conflicting signals)
        # We don't trigger other bottleneck rules
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
        
        logger.info("--- Step G: Completing Session 2 and checking fallback policy ---")
        session2, profile2 = await service.complete_session(db, session2.id)

    # Allow async tasks to settle
    await asyncio.sleep(0.5)

    async with SessionLocal() as db:
        c2_res = await db.execute(select(ConstraintORM).where(ConstraintORM.session_id == session2.id))
        constraints2 = list(c2_res.scalars().all())
        
        categories2 = [c.category for c in constraints2]
        logger.info(f"Identified constraints for Session 2: {categories2}")
        
        # It must trigger UNKNOWN category constraint
        assert "UNKNOWN" in categories2, "Expected UNKNOWN constraint from fallback conflict matching"
        
        unknown_c = [c for c in constraints2 if c.category == "UNKNOWN"][0]
        assert unknown_c.severity == "HIGH", "Unknown constraint should default to HIGH severity"
        assert unknown_c.confidence == 30, "Unknown constraint confidence should be 30"
        assert unknown_c.impact_score == 50, "Unknown constraint impact_score should be 50"
        assert "unknown_policy_audit" in unknown_c.origin, "Expected origin to track unknown_policy_audit"
        
        conflict_reasons = [e["reason"] for e in unknown_c.evidence if "Conflicting conversion metric" in e["reason"]]
        assert len(conflict_reasons) > 0, "Expected evidence reason auditing the conversion metric conflict"
        logger.info(f"Verified Unknown Constraint Policy evidence: {unknown_c.evidence}")

    logger.info("=========================================")
    logger.info("SUCCESS: Tvira Business Phase 4 (Constraint Classification) Verification Completed.")
    logger.info("=========================================")

if __name__ == "__main__":
    asyncio.run(run_constraints_verification())
