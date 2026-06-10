import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select
from app.core.database import SessionLocal, engine, Base
from app.models.applicability import ApplicabilityRuleORM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tvira.seed_applicability")

RULES = [
    {
        "name": "Customer Support AI Applicability Rule",
        "version": "1.0",
        "constraint_category": "CUSTOMER_SUPPORT",
        "conditions": {
            "field": "CUSTOMER_SUPPORT",
            "operator": "eq",
            "value": True
        },
        "applicability_score": 95,
        "confidence": 92,
        "category": "HIGHLY_APPLICABLE",
        "reasoning_template": "AI Receptionist is highly applicable to handle the identified customer support bottleneck with high confidence.",
        "recommended_solution_types": ["AI_RECEPTIONIST", "CUSTOMER_SUPPORT_AUTOMATION"]
    },
    {
        "name": "Lead Qualification AI Applicability Rule",
        "version": "1.0",
        "constraint_category": "LEAD_QUALIFICATION",
        "conditions": {
            "field": "LEAD_QUALIFICATION",
            "operator": "eq",
            "value": True
        },
        "applicability_score": 90,
        "confidence": 88,
        "category": "HIGHLY_APPLICABLE",
        "reasoning_template": "Lead Qualification automation can effectively organize incoming inquiries, reducing manual tracking overhead.",
        "recommended_solution_types": ["CRM_AUTOMATION", "LEAD_QUALIFICATION"]
    },
    {
        "name": "Scheduling AI Applicability Rule",
        "version": "1.0",
        "constraint_category": "SCHEDULING",
        "conditions": {
            "field": "SCHEDULING",
            "operator": "eq",
            "value": True
        },
        "applicability_score": 98,
        "confidence": 95,
        "category": "HIGHLY_APPLICABLE",
        "reasoning_template": "Booking coordination is highly structured and automatable using AI receptionist calendar bookings.",
        "recommended_solution_types": ["APPOINTMENT_SCHEDULING"]
    },
    {
        "name": "Operations Workflow AI Applicability Rule",
        "version": "1.0",
        "constraint_category": "OPERATIONS",
        "conditions": {
            "field": "OPERATIONS",
            "operator": "eq",
            "value": True
        },
        "applicability_score": 60,
        "confidence": 70,
        "category": "LOW_APPLICABILITY",
        "reasoning_template": "Operations workflows have lower applicability for AI automation due to custom human-in-the-loop dependencies.",
        "recommended_solution_types": ["WORKFLOW_AUTOMATION"]
    },
    {
        "name": "Team Management AI Applicability Rule",
        "version": "1.0",
        "constraint_category": "TEAM_MANAGEMENT",
        "conditions": {
            "field": "TEAM_MANAGEMENT",
            "operator": "eq",
            "value": True
        },
        "applicability_score": 20,
        "confidence": 60,
        "category": "NOT_RECOMMENDED",
        "reasoning_template": "Human team leadership and management have extremely low applicability for AI intervention.",
        "recommended_solution_types": ["WORKFLOW_AUTOMATION"]
    }
]

async def seed_applicability():
    async with engine.begin() as conn:
        # Import models so foreign keys can resolve
        from app.models.session import SessionORM
        from app.models.constraint import ConstraintORM
        from app.models.applicability import ApplicabilityRuleORM, AIApplicabilityORM, ReviewQueueORM
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        logger.info("Seeding AI applicability rules...")
        now = datetime.now(timezone.utc)
        for r in RULES:
            res = await db.execute(select(ApplicabilityRuleORM).where(ApplicabilityRuleORM.name == r["name"]))
            existing = res.scalars().first()
            if not existing:
                rule = ApplicabilityRuleORM(
                    id=uuid4(),
                    name=r["name"],
                    version=r["version"],
                    constraint_category=r["constraint_category"],
                    conditions=r["conditions"],
                    applicability_score=r["applicability_score"],
                    confidence=r["confidence"],
                    category=r["category"],
                    reasoning_template=r["reasoning_template"],
                    recommended_solution_types=r["recommended_solution_types"],
                    active=True,
                    created_at=now
                )
                db.add(rule)
                logger.info(f"Seeded applicability rule: {r['name']}")
            else:
                logger.info(f"Applicability rule {r['name']} already exists.")
        await db.commit()
        logger.info("AI applicability rule seeding complete.")

if __name__ == "__main__":
    asyncio.run(seed_applicability())
