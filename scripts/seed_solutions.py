import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select
from app.core.database import SessionLocal, engine, Base
from app.models.solution import SolutionCatalogORM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tvira.seed_solutions")

SOLUTIONS = [
    {
        "name": "AI Receptionist",
        "solution_type": "AI_RECEPTIONIST",
        "description": "Deploys an AI-powered conversational receptionist to handle phone calls, WhatsApp, and chat inquiries.",
        "supported_constraints": ["CUSTOMER_SUPPORT", "LEAD_QUALIFICATION", "SCHEDULING"],
        "supported_industries": ["*"],
        "minimum_applicability": 50,
        "active": True
    },
    {
        "name": "CRM Automation",
        "solution_type": "CRM_AUTOMATION",
        "description": "Centralizes leads list and automates tracking and routing logic.",
        "supported_constraints": ["LEAD_QUALIFICATION", "CUSTOMER_MANAGEMENT"],
        "supported_industries": ["*"],
        "minimum_applicability": 50,
        "active": True
    },
    {
        "name": "Appointment Scheduling",
        "solution_type": "APPOINTMENT_SCHEDULING",
        "description": "Automates calendar booking links to reduce appointment scheduling friction.",
        "supported_constraints": ["SCHEDULING"],
        "supported_industries": ["*"],
        "minimum_applicability": 50,
        "active": True
    },
    {
        "name": "Workflow Automation",
        "solution_type": "WORKFLOW_AUTOMATION",
        "description": "Automates manual data syncing, workflow processing, and task execution.",
        "supported_constraints": ["OPERATIONS"],
        "supported_industries": ["*"],
        "minimum_applicability": 50,
        "active": True
    },
    {
        "name": "Customer Support Automation",
        "solution_type": "CUSTOMER_SUPPORT_AUTOMATION",
        "description": "Automated ticketing, auto-responses, and support routing.",
        "supported_constraints": ["CUSTOMER_SUPPORT"],
        "supported_industries": ["*"],
        "minimum_applicability": 50,
        "active": True
    },
    {
        "name": "Document Processing",
        "solution_type": "DOCUMENT_PROCESSING",
        "description": "Extracts information from documents and integrates with database workflows.",
        "supported_constraints": ["DOCUMENT_WORKFLOW"],
        "supported_industries": ["*"],
        "minimum_applicability": 50,
        "active": True
    }
]

async def seed_solutions():
    async with engine.begin() as conn:
        from app.models.solution import SolutionCatalogORM, RecommendedSolutionORM
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        logger.info("Seeding solution catalog...")
        now = datetime.now(timezone.utc)
        for s in SOLUTIONS:
            res = await db.execute(select(SolutionCatalogORM).where(SolutionCatalogORM.solution_type == s["solution_type"]))
            existing = res.scalars().first()
            if not existing:
                sol = SolutionCatalogORM(
                    id=uuid4(),
                    name=s["name"],
                    solution_type=s["solution_type"],
                    description=s["description"],
                    supported_constraints=s["supported_constraints"],
                    supported_industries=s["supported_industries"],
                    minimum_applicability=s["minimum_applicability"],
                    active=s["active"],
                    created_at=now
                )
                db.add(sol)
                logger.info(f"Seeded solution: {s['name']}")
            else:
                logger.info(f"Solution {s['name']} already exists.")
        await db.commit()
        logger.info("Solution catalog seeding complete.")

if __name__ == "__main__":
    asyncio.run(seed_solutions())
