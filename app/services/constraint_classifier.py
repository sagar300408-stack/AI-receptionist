import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import SessionLocal
from app.models.session import SessionORM
from app.models.profile import BusinessProfileORM
from app.models.context import BusinessContextORM
from app.models.constraint import ConstraintRuleORM, ConstraintORM
from app.domain.entities.profile import BusinessProfile
from app.domain.entities.constraint import ConstraintRule, Constraint
from app.domain.policies.constraint import ConstraintClassificationPolicy
from app.domain.events.base import TviraDomainEvent, ConstraintsIdentifiedEvent
from app.services.event_bus import event_bus

logger = logging.getLogger("tvira.constraint_classifier")

class ConstraintClassifier:
    """Orchestrates loading session discovery profiles, executing constraint classification,
    persisting outcomes, and emitting constraints identified events.
    """

    async def classify_session_constraints(self, db: AsyncSession, session_id: UUID) -> List[ConstraintORM]:
        logger.info(f"Running constraint classification for session {session_id}...")

        # 1. Fetch Session & Profile
        session_orm = await db.get(SessionORM, session_id)
        if not session_orm:
            raise Exception(f"Session {session_id} not found.")

        p_query = select(BusinessProfileORM).where(BusinessProfileORM.session_id == session_id)
        p_result = await db.execute(p_query)
        profile_orm = p_result.scalars().first()
        if not profile_orm:
            raise Exception(f"Business Profile for session {session_id} not found.")

        # Map to domain entity
        profile_entity = BusinessProfile(
            id=profile_orm.id,
            session_id=profile_orm.session_id,
            industry=profile_orm.industry,
            business_type=profile_orm.business_type,
            team_size=profile_orm.team_size,
            monthly_leads=profile_orm.monthly_leads,
            monthly_customers=profile_orm.monthly_customers,
            business_stage=profile_orm.business_stage,
            communication_channels=profile_orm.communication_channels or [],
            pain_points=profile_orm.pain_points or [],
            goals=profile_orm.goals or [],
            profile_completion=profile_orm.profile_completion
        )

        # 2. Fetch context facts
        c_query = select(BusinessContextORM).where(BusinessContextORM.session_id == session_id)
        c_result = await db.execute(c_query)
        context_orm = c_result.scalars().first()
        context_facts = context_orm.facts if context_orm else {}

        # 3. Load active classification rules
        r_query = select(ConstraintRuleORM).where(ConstraintRuleORM.active == True)
        r_result = await db.execute(r_query)
        rule_orms = list(r_result.scalars().all())

        active_rules = []
        for ro in rule_orms:
            active_rules.append(
                ConstraintRule(
                    id=ro.id,
                    name=ro.name,
                    category=ro.category,
                    conditions=ro.conditions,
                    base_confidence=ro.base_confidence,
                    severity=ro.severity,
                    base_impact=ro.base_impact,
                    evidence_template=ro.evidence_template,
                    active=ro.active,
                    created_at=ro.created_at
                )
            )

        # 4. Classify constraints via Policy
        domain_constraints = ConstraintClassificationPolicy.classify(profile_entity, active_rules, context_facts)

        # 5. Clean existing constraints for this session
        del_query = select(ConstraintORM).where(ConstraintORM.session_id == session_id)
        del_result = await db.execute(del_query)
        for old in del_result.scalars().all():
            await db.delete(old)
        await db.commit()

        # 6. Persist Constraints to Database
        now = datetime.now(timezone.utc)
        constraint_orms = []
        serialized_constraints = []

        for dc in domain_constraints:
            c_orm = ConstraintORM(
                id=uuid4(),
                session_id=session_id,
                category=dc.category.value,
                confidence=dc.confidence,
                severity=dc.severity,
                impact_score=dc.impact_score,
                evidence=[e.model_dump() for e in dc.evidence],
                origin=dc.origin,
                created_at=now
            )
            db.add(c_orm)
            constraint_orms.append(c_orm)
            
            serialized_constraints.append({
                "category": dc.category.value,
                "confidence": dc.confidence,
                "severity": dc.severity,
                "impact_score": dc.impact_score,
                "evidence": [e.model_dump() for e in dc.evidence],
                "origin": dc.origin
            })

        await db.commit()
        logger.info(f"Persisted {len(constraint_orms)} constraints for session {session_id}.")

        # 7. Emit Constraints Identified Event
        event = ConstraintsIdentifiedEvent(
            session_id=session_id,
            business_profile_id=profile_orm.id,
            constraints=serialized_constraints,
            timestamp=now
        )
        await event_bus.publish(event)

        return constraint_orms

async def on_discovery_completed_listener(event: TviraDomainEvent):
    """Event subscriber intercepting DISCOVERY_COMPLETED to trigger constraint classification."""
    if event.event_type != "DISCOVERY_COMPLETED":
        return

    logger.info(f"Constraint classification listener intercepting DISCOVERY_COMPLETED for session {event.session_id}")
    
    async with SessionLocal() as db:
        try:
            classifier = ConstraintClassifier()
            await classifier.classify_session_constraints(db, event.session_id)
        except Exception as e:
            logger.error(f"Failed async constraint classification for session {event.session_id}: {e}")

def register_constraint_listeners():
    """Binds constraint classification subscriber to the domain Event Bus."""
    event_bus.subscribe("DISCOVERY_COMPLETED", on_discovery_completed_listener)
