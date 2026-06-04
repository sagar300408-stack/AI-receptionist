import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select
from app.core.database import SessionLocal
from app.models.report import ReportTemplateORM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tvira.seed_reports")

TEMPLATES = [
    {
        "name": "Coaching Report Template",
        "industry": "Coaching Institute",
        "structure": {
            "sections": [
                {"id": "exec_summary", "title": "Coaching Executive Summary", "order": 1},
                {"id": "health_index", "title": "Coaching Business Health Assessment", "order": 2},
                {"id": "priority_matrix", "title": "Coaching Opportunity Priority Matrix", "order": 3},
                {"id": "next_steps", "title": "Coaching Recommended Next Steps", "order": 4}
            ]
        }
    },
    {
        "name": "Real Estate Report Template",
        "industry": "Real Estate",
        "structure": {
            "sections": [
                {"id": "exec_summary", "title": "Real Estate Executive Summary", "order": 1},
                {"id": "health_index", "title": "Real Estate Business Health Assessment", "order": 2},
                {"id": "priority_matrix", "title": "Real Estate Opportunity Priority Matrix", "order": 3},
                {"id": "next_steps", "title": "Real Estate Recommended Next Steps", "order": 4}
            ]
        }
    },
    {
        "name": "Standard Business Report Layout",
        "industry": "Generic",
        "structure": {
            "sections": [
                {"id": "exec_summary", "title": "Executive Summary", "order": 1},
                {"id": "health_index", "title": "Business Health Assessment", "order": 2},
                {"id": "priority_matrix", "title": "Opportunity Priority Matrix", "order": 3},
                {"id": "next_steps", "title": "Recommended Next Steps", "order": 4}
            ]
        }
    }
]

async def seed_reports():
    async with SessionLocal() as db:
        logger.info("Seeding report templates...")
        now = datetime.now(timezone.utc)
        for t in TEMPLATES:
            res = await db.execute(select(ReportTemplateORM).where(ReportTemplateORM.name == t["name"]))
            existing = res.scalars().first()
            if not existing:
                template = ReportTemplateORM(
                    id=uuid4(),
                    name=t["name"],
                    industry=t["industry"],
                    structure=t["structure"],
                    active=True,
                    created_at=now
                )
                db.add(template)
                logger.info(f"Seeded report template: {t['name']}")
            else:
                logger.info(f"Report template {t['name']} already exists.")
        await db.commit()
        logger.info("Report template seeding complete.")

if __name__ == "__main__":
    asyncio.run(seed_reports())
