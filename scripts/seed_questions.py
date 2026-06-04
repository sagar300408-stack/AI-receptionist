import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import engine, Base, SessionLocal
from app.models.question import QuestionTemplateORM
from app.models.blueprint import DiscoveryBlueprintORM

# Configure Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tvira.seed")

# Core Question Templates
QUESTIONS = [
    {
        "question_key": "business_type",
        "question_text": "What type of business do you run? (e.g., Coaching Institute, Real Estate Agency, E-Commerce Store, Startup)",
        "industry": "Generic",
        "preconditions": {},
        "priority": 10,
        "required": True
    },
    {
        "question_key": "team_size",
        "question_text": "How many team members or employees do you currently have?",
        "industry": "Generic",
        "preconditions": {
            "field": "business_type",
            "operator": "ne",
            "value": None
        },
        "priority": 20,
        "required": True
    },
    {
        "question_key": "monthly_leads",
        "question_text": "How many leads or inquiries do you receive on average each month?",
        "industry": "Generic",
        "preconditions": {},
        "priority": 30,
        "required": True
    },
    {
        "question_key": "monthly_customers",
        "question_text": "How many monthly paying customers or active transactions do you process?",
        "industry": "Generic",
        "preconditions": {},
        "priority": 40,
        "required": True
    },
    {
        "question_key": "coaching_inquiries",
        "question_text": "With student enrollments, how are you currently managing admissions tracking and counselor workload?",
        "industry": "Coaching Institute",
        "preconditions": {
            "field": "industry",
            "operator": "eq",
            "value": "Coaching Institute"
        },
        "priority": 45,
        "required": False
    },
    {
        "question_key": "real_estate_followup",
        "question_text": "How do agents coordinate property site visits and follow up with buyer inquiries?",
        "industry": "Real Estate",
        "preconditions": {
            "field": "industry",
            "operator": "eq",
            "value": "Real Estate"
        },
        "priority": 45,
        "required": False
    },
    {
        "question_key": "communication_channels",
        "question_text": "What channels do clients use most to reach you? (e.g., WhatsApp, Website form, Phone calls, Email, Instagram)",
        "industry": "Generic",
        "preconditions": {},
        "priority": 50,
        "required": True
    },
    {
        "question_key": "pain_points",
        "question_text": "What tasks consume the most manual hours weekly or represent your biggest operational bottleneck?",
        "industry": "Generic",
        "preconditions": {},
        "priority": 60,
        "required": True
    },
    {
        "question_key": "goals",
        "question_text": "What are your primary automation and business operational goals over the next six months?",
        "industry": "Generic",
        "preconditions": {},
        "priority": 70,
        "required": True
    }
]

# Discovery Blueprints
BLUEPRINTS = [
    {
        "name": "Generic Discovery Blueprint",
        "industry": "Generic",
        "version": "v1",
        "stages": ["Business Identification", "Team Scale", "Activity Metrics", "Communication Channel Check", "Pain Point Deep-Dive", "Growth Objectives"],
        "active": True
    },
    {
        "name": "Coaching Discovery Blueprint",
        "industry": "Coaching Institute",
        "version": "v1",
        "stages": ["Business Identification", "Team Scale", "Activity Metrics", "Counselor Operations", "Communication Channel Check", "Pain Point Deep-Dive", "Growth Objectives"],
        "active": True
    },
    {
        "name": "Real Estate Discovery Blueprint",
        "industry": "Real Estate",
        "version": "v1",
        "stages": ["Business Identification", "Team Scale", "Activity Metrics", "Broker Operations", "Communication Channel Check", "Pain Point Deep-Dive", "Growth Objectives"],
        "active": True
    }
]

async def seed_data():
    # 1. Initialize tables first
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        logger.info("Seeding question templates...")
        for q in QUESTIONS:
            # Check if template already exists
            res = await db.execute(
                select(QuestionTemplateORM).where(QuestionTemplateORM.question_key == q["question_key"])
            )
            existing = res.scalars().first()
            if not existing:
                template = QuestionTemplateORM(
                    id=uuid4(),
                    question_key=q["question_key"],
                    question_text=q["question_text"],
                    industry=q["industry"],
                    preconditions=q["preconditions"],
                    priority=q["priority"],
                    required=q["required"],
                    active=True
                )
                db.add(template)
                logger.info(f"Added question template: {q['question_key']}")
            else:
                logger.info(f"Question template {q['question_key']} already exists, skipping.")

        logger.info("Seeding discovery blueprints...")
        now = datetime.now(timezone.utc)
        for bp in BLUEPRINTS:
            res = await db.execute(
                select(DiscoveryBlueprintORM).where(
                    DiscoveryBlueprintORM.name == bp["name"], 
                    DiscoveryBlueprintORM.version == bp["version"]
                )
            )
            existing = res.scalars().first()
            if not existing:
                blueprint = DiscoveryBlueprintORM(
                    id=uuid4(),
                    name=bp["name"],
                    industry=bp["industry"],
                    version=bp["version"],
                    stages=bp["stages"],
                    active=bp["active"],
                    created_at=now
                )
                db.add(blueprint)
                logger.info(f"Added blueprint: {bp['name']}")
            else:
                logger.info(f"Blueprint {bp['name']} already exists, skipping.")

        await db.commit()
        logger.info("Seeding completed successfully.")

if __name__ == "__main__":
    asyncio.run(seed_data())
