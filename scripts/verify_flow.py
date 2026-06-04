import os
import asyncio
import logging
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select
from app.core.database import engine, Base, SessionLocal
from app.models.session import SessionORM
from app.models.profile import BusinessProfileORM
from app.models.response import UserResponseORM
from app.models.event import SessionEventORM
from app.models.context import BusinessContextORM
from scripts.seed_questions import seed_data
from app.services.session import SessionService

from app.services.event_store_listener import register_db_event_listener

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tvira.verification")

async def run_verification():
    logger.info("Starting Tvira Business Discovery Engine E2E Verification...")
    
    # Register event subscribers for DB persistence
    register_db_event_listener()

    # 1. Clean database state if SQLite is used
    db_file = "./tvira_business.db"
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
            logger.info("Removed existing test database for clean run.")
        except Exception as e:
            logger.warning(f"Could not remove database file: {e}")

    # 2. Run Seed Script to initialize database and seed templates/blueprints
    await seed_data()
    logger.info("Database initialized and seeded.")

    # 3. Instantiate SessionService (main orchestrator)
    service = SessionService()

    async with SessionLocal() as db:
        # A. Start a new session
        logger.info("--- Step A: Creating Session ---")
        session, profile = await service.create_session(db)
        assert session.status.value == "CREATED", f"Expected status CREATED, got {session.status.value}"
        assert profile.profile_completion == 0.0, f"Expected completion 0%, got {profile.profile_completion}%"
        logger.info(f"Session created. ID: {session.id}, Token: {session.session_token}")

        # B. Answer Question 1: business_type -> Coaching Institute
        logger.info("--- Step B: Answering business_type ---")
        session, profile, next_text = await service.respond_to_question(
            db, session.id, "business_type", "Coaching Institute"
        )
        assert session.status.value == "DISCOVERY_IN_PROGRESS"
        assert profile.business_type == "Coaching Institute"
        assert profile.industry == "Coaching Institute"
        assert session.progress_state.current_key == "team_size", f"Expected next question team_size, got {session.progress_state.current_key}"
        logger.info(f"Q1 answered. Next question text: '{next_text}'")

        # C. Answer Question 2: team_size -> 12 people
        logger.info("--- Step C: Answering team_size ---")
        session, profile, next_text = await service.respond_to_question(
            db, session.id, "team_size", "We have a team of 12 people"
        )
        assert profile.team_size == 12
        assert profile.business_stage == "GROWTH"
        assert session.progress_state.current_key == "monthly_leads"
        logger.info(f"Q2 answered. Next question text: '{next_text}'")

        # D. Answer Question 3: monthly_leads -> 600 inquiries
        logger.info("--- Step D: Answering monthly_leads ---")
        session, profile, next_text = await service.respond_to_question(
            db, session.id, "monthly_leads", "About 600 monthly inquiries"
        )
        assert profile.monthly_leads == 600
        assert session.progress_state.current_key == "monthly_customers"
        logger.info(f"Q3 answered. Next question text: '{next_text}'")

        # E. Answer Question 4: monthly_customers -> 150 student enrollments
        logger.info("--- Step E: Answering monthly_customers ---")
        session, profile, next_text = await service.respond_to_question(
            db, session.id, "monthly_customers", "We handle 150 student enrollments each month"
        )
        assert profile.monthly_customers == 150
        # The next question should adapt to Coaching specific: coaching_inquiries
        assert session.progress_state.current_key == "coaching_inquiries", f"Expected coaching_inquiries, got {session.progress_state.current_key}"
        logger.info(f"Q4 answered. Next question text: '{next_text}'")

        # F. Answer Question 5: coaching_inquiries -> Spreadsheet trackers
        logger.info("--- Step F: Answering coaching_inquiries ---")
        session, profile, next_text = await service.respond_to_question(
            db, session.id, "coaching_inquiries", "Admissions are tracked on spreadsheets, counselor workloads are high."
        )
        assert session.progress_state.current_key == "communication_channels"
        logger.info(f"Q5 answered. Next question text: '{next_text}'")

        # G. Answer Question 6: communication_channels -> WhatsApp and Email
        logger.info("--- Step G: Answering communication_channels ---")
        session, profile, next_text = await service.respond_to_question(
            db, session.id, "communication_channels", "Customers reach us via WhatsApp and Email mainly"
        )
        assert "WhatsApp" in profile.communication_channels
        assert "Email" in profile.communication_channels
        assert session.progress_state.current_key == "pain_points"
        logger.info(f"Q6 answered. Next question text: '{next_text}'")

        # H. Answer Question 7: pain_points -> Manual typing and follow-up delays
        logger.info("--- Step H: Answering pain_points ---")
        session, profile, next_text = await service.respond_to_question(
            db, session.id, "pain_points", "Delayed followups and manual entry"
        )
        assert len(profile.pain_points) > 0
        assert session.progress_state.current_key == "goals"
        logger.info(f"Q7 answered. Next question text: '{next_text}'")

        # I. Answer Question 8: goals -> Automate followups and status dashboard
        logger.info("--- Step I: Answering goals ---")
        session, profile, next_text = await service.respond_to_question(
            db, session.id, "goals", "We want to automate counselor reminders and student status tracking"
        )
        assert len(profile.goals) > 0
        assert next_text is None or session.progress_state.current_key is None, f"Expected no more questions, got {session.progress_state.current_key}"
        logger.info("Discovery questionnaire complete.")

        # J. Complete Session and evaluate Business Context (v1 facts)
        logger.info("--- Step J: Completing Session ---")
        session, profile = await service.complete_session(db, session.id)
        assert session.status.value == "PROFILE_GENERATED"
        logger.info("Session marked completed and profile generated.")

        # Verify Business Context DB entries
        ctx_res = await db.execute(select(BusinessContextORM).where(BusinessContextORM.session_id == session.id))
        context_orm = ctx_res.scalars().first()
        assert context_orm is not None
        assert context_orm.context_version == "v1"
        assert context_orm.facts["lead_volume_tier"] == "HIGH", f"Expected HIGH lead volume tier, got {context_orm.facts['lead_volume_tier']}"
        assert context_orm.facts["operational_complexity"] == "MEDIUM"
        assert context_orm.facts["business_maturity"] == "GROWTH"
        logger.info(f"Verified Business Context Facts: {context_orm.facts}")

        # K. Perform Lead Capture
        logger.info("--- Step K: Lead Capture ---")
        session = await service.capture_lead(db, session.id, "Dr. Sarah Paul", "sarah@academy.com", "+1-999-888-7777")
        assert session.status.value == "LEAD_CAPTURED"
        logger.info("Lead captured successfully.")

        # L. Final verification of Database Logs and Event persistence
        logger.info("--- Step L: Database Audit & Event Bus Check ---")
        
        # Verify event storage
        event_res = await db.execute(select(SessionEventORM).where(SessionEventORM.session_id == session.id))
        events = list(event_res.scalars().all())
        event_types = [e.event_type for e in events]
        logger.info(f"Dispatched database audit events: {event_types}")
        
        assert "SESSION_CREATED" in event_types
        assert "PROFILE_UPDATED" in event_types
        assert "DISCOVERY_COMPLETED" in event_types
        assert "PROFILE_GENERATED" in event_types
        assert "LEAD_CAPTURED" in event_types

        # Verify profile records are fully populated
        p_res = await db.execute(select(BusinessProfileORM).where(BusinessProfileORM.session_id == session.id))
        prof_orm = p_res.scalars().first()
        assert prof_orm.industry == "Coaching Institute"
        assert prof_orm.team_size == 12
        assert prof_orm.profile_completion == 100.0, f"Expected 100% completion, got {prof_orm.profile_completion}%"
        logger.info(f"Business Profile completion validated: {prof_orm.profile_completion}%")

    logger.info("=========================================")
    logger.info("SUCCESS: Tvira Business Discovery Engine Verification Completed.")
    logger.info("=========================================")

if __name__ == "__main__":
    asyncio.run(run_verification())
