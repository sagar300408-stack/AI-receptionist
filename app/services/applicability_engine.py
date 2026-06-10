import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.core.database import SessionLocal
from app.models.session import SessionORM
from app.models.profile import BusinessProfileORM
from app.models.context import BusinessContextORM
from app.models.constraint import ConstraintORM
from app.models.applicability import ApplicabilityRuleORM, AIApplicabilityORM, ReviewQueueORM
from app.domain.entities.profile import BusinessProfile
from app.domain.entities.constraint import Constraint
from app.domain.value_objects.constraint import ConstraintCategory, ConstraintEvidence
from app.domain.applicability import (
    ApplicabilityRule,
    AIApplicability,
    ApplicabilityEvidence,
    SolutionType,
    ApplicabilityCategory,
    ApplicabilityEvaluationPolicy
)
from app.domain.events.base import TviraDomainEvent, ApplicabilityAnalyzedEvent
from app.services.event_bus import event_bus

logger = logging.getLogger("tvira.applicability_engine")

class AIApplicabilityEngine:
    """Orchestrates loading session constraints, evaluating AI applicability rules,
    populating the manual review queue, and emitting events.
    """

    async def evaluate_session_applicability(self, db: AsyncSession, session_id: UUID) -> List[AIApplicabilityORM]:
        logger.info(f"Running AI applicability engine for session {session_id}...")

        # 1. Fetch Session & Profile
        session_orm = await db.get(SessionORM, session_id)
        if not session_orm:
            raise Exception(f"Session {session_id} not found.")

        p_query = select(BusinessProfileORM).where(BusinessProfileORM.session_id == session_id)
        p_result = await db.execute(p_query)
        profile_orm = p_result.scalars().first()
        if not profile_orm:
            raise Exception(f"Business Profile for session {session_id} not found.")

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

        # 2. Fetch Derived Context Facts
        c_query = select(BusinessContextORM).where(BusinessContextORM.session_id == session_id)
        c_result = await db.execute(c_query)
        context_orm = c_result.scalars().first()
        context_facts = context_orm.facts if context_orm else {}

        # 3. Fetch Constraints for the session
        const_query = select(ConstraintORM).where(ConstraintORM.session_id == session_id)
        const_result = await db.execute(const_query)
        constraint_orms = list(const_result.scalars().all())

        if not constraint_orms:
            logger.warning(f"No constraints found for session {session_id}. Applicability evaluation empty.")
            # Even if empty, let's clean up existing and publish event
            await self._cleanup_existing(db, session_id)
            event = ApplicabilityAnalyzedEvent(session_id=session_id, applicability_results=[], timestamp=datetime.now(timezone.utc))
            await event_bus.publish(event)
            return []

        # Map to domain constraints
        constraints = []
        for co in constraint_orms:
            evidences = []
            if isinstance(co.evidence, list):
                for ev in co.evidence:
                    if isinstance(ev, dict):
                        evidences.append(
                            ConstraintEvidence(
                                source=ev.get("source", "unknown"),
                                value=ev.get("value"),
                                reason=ev.get("reason", "")
                            )
                        )
            constraints.append(
                Constraint(
                    id=co.id,
                    session_id=co.session_id,
                    category=ConstraintCategory(co.category),
                    confidence=co.confidence,
                    severity=co.severity,
                    impact_score=co.impact_score,
                    evidence=evidences,
                    origin=co.origin or [],
                    created_at=co.created_at
                )
            )

        # Add constraints info to facts for dynamic conditions
        for c in constraints:
            context_facts[c.category.value] = True
            context_facts[f"{c.category.value}_severity"] = c.severity
            context_facts[f"{c.category.value}_confidence"] = c.confidence
            context_facts[f"{c.category.value}_impact"] = c.impact_score

        # 4. Load Active Applicability Rules
        r_query = select(ApplicabilityRuleORM).where(ApplicabilityRuleORM.active == True)
        r_result = await db.execute(r_query)
        rule_orms = list(r_result.scalars().all())

        active_rules = []
        for ro in rule_orms:
            active_rules.append(
                ApplicabilityRule(
                    id=ro.id,
                    name=ro.name,
                    version=ro.version,
                    constraint_category=ro.constraint_category,
                    conditions=ro.conditions,
                    applicability_score=ro.applicability_score,
                    confidence=ro.confidence,
                    category=ApplicabilityCategory(ro.category),
                    reasoning_template=ro.reasoning_template,
                    recommended_solution_types=[SolutionType(st) for st in ro.recommended_solution_types],
                    active=ro.active,
                    created_at=ro.created_at
                )
            )

        # 5. Clean existing AI Applicability & Review Queue entries for the session
        await self._cleanup_existing(db, session_id)

        # 6. Evaluate and Save results
        now = datetime.now(timezone.utc)
        applicability_orms = []
        serialized_results = []
        review_queue_entries = []

        for c in constraints:
            app_result = ApplicabilityEvaluationPolicy.evaluate(
                profile_entity, c, active_rules, context_facts
            )

            # Persist ORM model
            app_orm = AIApplicabilityORM(
                id=uuid4(),
                session_id=session_id,
                constraint_id=c.id,
                applicability_score=app_result.applicability_score,
                confidence=app_result.confidence,
                category=app_result.category.value,
                reasoning=app_result.reasoning,
                evidence=[e.model_dump() for e in app_result.evidence],
                recommended_solution_types=[st.value for st in app_result.recommended_solution_types],
                rule_version=app_result.rule_version,
                created_at=now
            )
            db.add(app_orm)
            applicability_orms.append(app_orm)

            serialized_results.append({
                "constraint_category": c.category.value,
                "applicability_score": app_result.applicability_score,
                "confidence": app_result.confidence,
                "category": app_result.category.value,
                "reasoning": app_result.reasoning,
                "evidence": [e.model_dump() for e in app_result.evidence],
                "recommended_solution_types": [st.value for st in app_result.recommended_solution_types],
                "rule_version": app_result.rule_version
            })

            # Check review queue criteria
            trigger_review = False
            review_reason = ""
            review_priority = "LOW"

            # Criterion A: constraint category is UNKNOWN
            if c.category == ConstraintCategory.UNKNOWN:
                trigger_review = True
                review_reason = "Constraint category is UNKNOWN, requiring manual triage."
                review_priority = "HIGH"

            # Criterion B: applicability score < 40
            elif app_result.applicability_score < 40:
                trigger_review = True
                review_reason = f"Low AI applicability score ({app_result.applicability_score}) calculated for bottleneck: {c.category.value}."
                review_priority = "HIGH"

            # Criterion C: no applicability rule matches (version N/A)
            elif app_result.rule_version == "N/A":
                trigger_review = True
                review_reason = f"No active AI applicability rules matched constraint category: {c.category.value}."
                review_priority = "HIGH"

            # Criterion D: conflicting applicability results occur
            # e.g., high leads volume but zero customer conversion while resolving high AI applicability
            leads = profile_entity.monthly_leads or 0
            customers = profile_entity.monthly_customers or 0
            if leads >= 500 and customers <= 0 and app_result.applicability_score >= 70:
                trigger_review = True
                review_reason = f"Conflicting metric audit: High leads ({leads}) but zero customers conversion, while resolved applicability score is high ({app_result.applicability_score})."
                review_priority = "HIGH"

            if trigger_review:
                review_orm = ReviewQueueORM(
                    id=uuid4(),
                    session_id=session_id,
                    constraint_id=c.id,
                    reason=review_reason,
                    priority=review_priority,
                    created_at=now
                )
                db.add(review_orm)
                review_queue_entries.append(review_orm)
                logger.info(f"Added constraint {c.category.value} to review queue. Priority: {review_priority}.")

        await db.commit()
        logger.info(f"Persisted {len(applicability_orms)} applicability results & {len(review_queue_entries)} review queue entries.")

        # 7. Emit Applicability Analyzed Event
        event = ApplicabilityAnalyzedEvent(
            session_id=session_id,
            applicability_results=serialized_results,
            timestamp=now
        )
        await event_bus.publish(event)

        return applicability_orms

    async def _cleanup_existing(self, db: AsyncSession, session_id: UUID):
        """Cleans up existing applicability and review queue entries for a session to prevent duplicates."""
        await db.execute(delete(AIApplicabilityORM).where(AIApplicabilityORM.session_id == session_id))
        await db.execute(delete(ReviewQueueORM).where(ReviewQueueORM.session_id == session_id))
        await db.commit()

async def on_constraints_identified_listener(event: TviraDomainEvent):
    """Event listener catching CONSTRAINTS_IDENTIFIED to trigger AI applicability evaluations."""
    if event.event_type != "CONSTRAINTS_IDENTIFIED":
        return

    logger.info(f"AI Applicability subscriber intercepting CONSTRAINTS_IDENTIFIED for session: {event.session_id}")
    
    async with SessionLocal() as db:
        try:
            engine = AIApplicabilityEngine()
            await engine.evaluate_session_applicability(db, event.session_id)
        except Exception as e:
            logger.error(f"Async AI applicability evaluation failed for session {event.session_id}: {e}")

def register_applicability_listeners():
    """Binds the AI applicability engine listener to the domain Event Bus."""
    event_bus.subscribe("CONSTRAINTS_IDENTIFIED", on_constraints_identified_listener)
