import asyncio
import logging
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from sqlalchemy import select
from app.core.database import engine, Base, SessionLocal
from app.models.opportunity import (
    OpportunityGroupORM, OpportunityTemplateORM, OpportunityRuleORM, ScoringProfileORM
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tvira.seed_opportunities")

GROUPS = [
    {"name": "Customer Communication", "category": "Communication", "description": "AI receptionist and channels automation"},
    {"name": "Lead Management System", "category": "Lead Management", "description": "CRM tracking and automated lead distribution"},
    {"name": "Operations Automation", "category": "Operations", "description": "Data entry sync, appointment booking, and workflow scripts"}
]

SCORING_PROFILE = {
    "name": "Standard Business Profile",
    "thresholds": {
        "critical": {"impact": 80, "complexity": 40},
        "high": {"impact": 60, "complexity": 60},
        "medium": {"impact": 40, "complexity": 80}
    }
}

TEMPLATES = [
    {
        "code": "AI_RECEPTIONIST",
        "name": "AI Receptionist Chatbot",
        "group_name": "Customer Communication",
        "version": "v1",
        "description": "Deploys an AI-powered conversational receptionist to handle WhatsApp inquiries.",
        "base_impact": 70.0,
        "base_complexity": 30.0,
        "rules": [
            {
                "rule_type": "ELIGIBILITY",
                "conditions": {"field": "monthly_leads", "operator": "gt", "value": 100},
                "modifier_value": None,
                "explanation_template": None
            },
            {
                "rule_type": "REASONING",
                "conditions": {"field": "monthly_leads", "operator": "gt", "value": 300},
                "modifier_value": None,
                "explanation_template": "High inquiry volume ({monthly_leads} leads/month) results in slow manual response times."
            },
            {
                "rule_type": "REASONING",
                "conditions": {"field": "communication_channels", "operator": "contains", "value": "WhatsApp"},
                "modifier_value": None,
                "explanation_template": "Customers reach out via WhatsApp, requiring continuous manual tracking."
            },
            {
                "rule_type": "IMPACT_MODIFIER",
                "conditions": {"field": "pain_points", "operator": "contains", "value": "Delayed followups"},
                "modifier_value": 15.0,
                "explanation_template": None
            }
        ]
    },
    {
        "code": "CRM_AUTOMATION",
        "name": "CRM & Lead Routing System",
        "group_name": "Lead Management System",
        "version": "v1",
        "description": "Centralizes prospects list and automates lead routing rules to counselors/brokers.",
        "base_impact": 60.0,
        "base_complexity": 40.0,
        "rules": [
            {
                "rule_type": "ELIGIBILITY",
                "conditions": {"field": "team_size", "operator": "gt", "value": 2},
                "modifier_value": None,
                "explanation_template": None
            },
            {
                "rule_type": "REASONING",
                "conditions": {"field": "team_size", "operator": "gt", "value": 5},
                "modifier_value": None,
                "explanation_template": "Friction in manually coordinating assignments across {team_size} team members."
            },
            {
                "rule_type": "REASONING",
                "conditions": {"field": "pain_points", "operator": "contains", "value": "Admissions are tracked on spreadsheets"},
                "modifier_value": None,
                "explanation_template": "Using manual spreadsheets for tracking leads leads to data leakage and poor auditing."
            },
            {
                "rule_type": "IMPACT_MODIFIER",
                "conditions": {"field": "lead_volume_tier", "operator": "eq", "value": "HIGH"},
                "modifier_value": 20.0,
                "explanation_template": None
            }
        ]
    },
    {
        "code": "APPOINTMENT_SCHEDULING",
        "name": "Automated Appointment Scheduling",
        "group_name": "Operations Automation",
        "version": "v1",
        "description": "Integrated calendar booking links to reduce appointment scheduling friction.",
        "base_impact": 50.0,
        "base_complexity": 20.0,
        "rules": [
            {
                "rule_type": "ELIGIBILITY",
                "conditions": {"field": "monthly_customers", "operator": "gt", "value": 50},
                "modifier_value": None,
                "explanation_template": None
            },
            {
                "rule_type": "REASONING",
                "conditions": {"field": "monthly_customers", "operator": "gt", "value": 100},
                "modifier_value": None,
                "explanation_template": "A high volume of monthly transactions ({monthly_customers} customers) increases schedule coordination overhead."
            },
            {
                "rule_type": "IMPACT_MODIFIER",
                "conditions": {"field": "pain_points", "operator": "contains", "value": "Scheduling visits"},
                "modifier_value": 25.0,
                "explanation_template": None
            }
        ]
    }
]

async def seed_opportunities():
    async with SessionLocal() as db:
        logger.info("Seeding opportunity groups...")
        group_id_map = {}
        for g in GROUPS:
            res = await db.execute(select(OpportunityGroupORM).where(OpportunityGroupORM.name == g["name"]))
            existing = res.scalars().first()
            if not existing:
                group = OpportunityGroupORM(
                    id=uuid4(),
                    name=g["name"],
                    category=g["category"],
                    description=g["description"],
                    active=True
                )
                db.add(group)
                group_id_map[g["name"]] = group.id
                logger.info(f"Seeded group: {g['name']}")
            else:
                group_id_map[g["name"]] = existing.id
                logger.info(f"Group {g['name']} exists.")

        logger.info("Seeding scoring profiles...")
        res = await db.execute(select(ScoringProfileORM).where(ScoringProfileORM.name == SCORING_PROFILE["name"]))
        existing_profile = res.scalars().first()
        if not existing_profile:
            profile = ScoringProfileORM(
                id=uuid4(),
                name=SCORING_PROFILE["name"],
                thresholds=SCORING_PROFILE["thresholds"],
                active=True,
                created_at=datetime.now(timezone.utc)
            )
            db.add(profile)
            logger.info(f"Seeded scoring profile: {profile.name}")
        else:
            logger.info("Scoring profile exists.")

        logger.info("Seeding opportunity templates & rules...")
        now = datetime.now(timezone.utc)
        for t in TEMPLATES:
            res = await db.execute(select(OpportunityTemplateORM).where(
                OpportunityTemplateORM.code == t["code"],
                OpportunityTemplateORM.version == t["version"]
            ))
            existing_template = res.scalars().first()
            
            group_id = group_id_map.get(t["group_name"])

            if not existing_template:
                template = OpportunityTemplateORM(
                    id=uuid4(),
                    group_id=group_id,
                    code=t["code"],
                    name=t["name"],
                    version=t["version"],
                    description=t["description"],
                    base_impact=t["base_impact"],
                    base_complexity=t["base_complexity"],
                    active=True,
                    effective_from=now - timedelta(days=1),
                    effective_to=now + timedelta(days=365),
                    created_at=now,
                    updated_at=now
                )
                db.add(template)
                await db.commit()
                await db.refresh(template)
                logger.info(f"Seeded template: {t['code']}")
                
                # Add rules
                for r in t["rules"]:
                    rule = OpportunityRuleORM(
                        id=uuid4(),
                        template_id=template.id,
                        rule_type=r["rule_type"],
                        conditions=r["conditions"],
                        modifier_value=r["modifier_value"],
                        explanation_template=r["explanation_template"],
                        active=True,
                        created_at=now
                    )
                    db.add(rule)
                logger.info(f"Seeded rules for: {t['code']}")
            else:
                logger.info(f"Template {t['code']} (version: {t['version']}) already exists.")

        await db.commit()
        logger.info("Opportunity catalog seeding complete.")

if __name__ == "__main__":
    asyncio.run(seed_opportunities())
