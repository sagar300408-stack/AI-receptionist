import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select
from app.core.database import SessionLocal
from app.models.constraint import ConstraintRuleORM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tvira.seed_constraints")

RULES = [
    {
        "name": "Customer Support Bottleneck Rule",
        "category": "CUSTOMER_SUPPORT",
        "conditions": {
            "or": [
                {"field": "pain_points", "operator": "contains", "value": "Slow responses"},
                {"field": "pain_points", "operator": "contains", "value": "Too many phone calls"},
                {"field": "pain_points", "operator": "contains", "value": "Delayed followups"}
            ]
        },
        "base_confidence": 90,
        "severity": "HIGH",
        "base_impact": 85,
        "evidence_template": "Customer communication channels require manual tracking with reported bottleneck: {pain_point}"
    },
    {
        "name": "Lead Qualification Bottleneck Rule",
        "category": "LEAD_QUALIFICATION",
        "conditions": {
            "or": [
                {"field": "pain_points", "operator": "contains", "value": "Admissions are tracked on spreadsheets"},
                {"field": "pain_points", "operator": "contains", "value": "manual tracking"},
                {"field": "monthly_leads", "operator": "gt", "value": 500}
            ]
        },
        "base_confidence": 85,
        "severity": "HIGH",
        "base_impact": 80,
        "evidence_template": "Inquiry volume of {monthly_leads} leads combined with spreadsheet tracking bottlenecks qualification."
    },
    {
        "name": "Scheduling Bottleneck Rule",
        "category": "SCHEDULING",
        "conditions": {
            "or": [
                {"field": "pain_points", "operator": "contains", "value": "Scheduling visits"},
                {"field": "pain_points", "operator": "contains", "value": "scheduling friction"},
                {"field": "monthly_customers", "operator": "gt", "value": 100}
            ]
        },
        "base_confidence": 80,
        "severity": "MEDIUM",
        "base_impact": 65,
        "evidence_template": "Transaction flow of {monthly_customers} monthly customers introduces scheduling coordination bottlenecks."
    },
    {
        "name": "Operations Workflow Rule",
        "category": "OPERATIONS",
        "conditions": {
            "or": [
                {"field": "team_size", "operator": "gt", "value": 5},
                {"field": "goals", "operator": "contains", "value": "Automate counselor workflow"}
            ]
        },
        "base_confidence": 75,
        "severity": "MEDIUM",
        "base_impact": 70,
        "evidence_template": "Team size of {team_size} members requires automated routing to avoid manual workflow coordination bottlenecks."
    }
]

async def seed_constraints():
    from app.core.database import engine, Base
    async with engine.begin() as conn:
        from app.models.constraint import ConstraintRuleORM, ConstraintORM
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        logger.info("Seeding constraint classification rules...")
        now = datetime.now(timezone.utc)
        for r in RULES:
            res = await db.execute(select(ConstraintRuleORM).where(ConstraintRuleORM.name == r["name"]))
            existing = res.scalars().first()
            if not existing:
                rule = ConstraintRuleORM(
                    id=uuid4(),
                    name=r["name"],
                    category=r["category"],
                    conditions=r["conditions"],
                    base_confidence=r["base_confidence"],
                    severity=r["severity"],
                    base_impact=r["base_impact"],
                    evidence_template=r["evidence_template"],
                    active=True,
                    created_at=now
                )
                db.add(rule)
                logger.info(f"Seeded constraint rule: {r['name']}")
            else:
                logger.info(f"Constraint rule {r['name']} already exists.")
        await db.commit()
        logger.info("Constraint rule seeding complete.")

if __name__ == "__main__":
    asyncio.run(seed_constraints())
