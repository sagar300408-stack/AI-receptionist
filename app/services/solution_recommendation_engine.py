import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.core.database import SessionLocal
from app.models.session import SessionORM
from app.models.profile import BusinessProfileORM
from app.models.constraint import ConstraintORM
from app.models.applicability import AIApplicabilityORM
from app.models.solution import SolutionCatalogORM, RecommendedSolutionORM
from app.domain.entities.profile import BusinessProfile
from app.domain.entities.constraint import Constraint
from app.domain.value_objects.constraint import ConstraintCategory, ConstraintEvidence
from app.domain.applicability import AIApplicability, ApplicabilityCategory, ApplicabilityEvidence, SolutionType
from app.domain.solution import (
    SolutionCatalog,
    RecommendedSolution,
    SolutionEvidence,
    SolutionRecommendationPolicy,
)
from app.domain.events.base import TviraDomainEvent, SolutionsRecommendedEvent
from app.services.event_bus import event_bus

logger = logging.getLogger("tvira.solution_recommendation_engine")

class SolutionRecommendationEngine:
    """Orchestrates loading AI applicability results, matching against the solution catalog,
    persisting recommended solutions, and emitting events.
    """

    async def evaluate_session_solutions(self, db: AsyncSession, session_id: UUID) -> List[RecommendedSolutionORM]:
        logger.info(f"Running Solution Recommendation Engine for session {session_id}...")

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

        # 2. Fetch Constraints for the session
        const_query = select(ConstraintORM).where(ConstraintORM.session_id == session_id)
        const_result = await db.execute(const_query)
        constraint_orms = list(const_result.scalars().all())

        if not constraint_orms:
            logger.warning(f"No constraints found for session {session_id}. Solution recommendations empty.")
            await self._cleanup_existing(db, session_id)
            event = SolutionsRecommendedEvent(session_id=session_id, recommended_solutions=[], timestamp=datetime.now(timezone.utc))
            await event_bus.publish(event)
            return []

        # Map to domain constraints
        constraints_map = {}
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
            constraint_entity = Constraint(
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
            constraints_map[co.id] = constraint_entity

        # 3. Fetch AI Applicability for the session
        app_query = select(AIApplicabilityORM).where(AIApplicabilityORM.session_id == session_id)
        app_result = await db.execute(app_query)
        app_orms = list(app_result.scalars().all())

        if not app_orms:
            logger.warning(f"No applicability results found for session {session_id}. Solution recommendations empty.")
            await self._cleanup_existing(db, session_id)
            event = SolutionsRecommendedEvent(session_id=session_id, recommended_solutions=[], timestamp=datetime.now(timezone.utc))
            await event_bus.publish(event)
            return []

        # Map to domain applicability
        applicabilities: List[AIApplicability] = []
        for ao in app_orms:
            evidence_items = []
            if isinstance(ao.evidence, list):
                for ev in ao.evidence:
                    if isinstance(ev, dict):
                        evidence_items.append(
                            ApplicabilityEvidence(
                                source=ev.get("source", "unknown"),
                                value=ev.get("value"),
                                reason=ev.get("reason", "")
                            )
                        )
            applicabilities.append(
                AIApplicability(
                    id=ao.id,
                    session_id=ao.session_id,
                    constraint_id=ao.constraint_id,
                    applicability_score=ao.applicability_score,
                    confidence=ao.confidence,
                    category=ApplicabilityCategory(ao.category),
                    reasoning=ao.reasoning,
                    evidence=evidence_items,
                    recommended_solution_types=[SolutionType(st) for st in ao.recommended_solution_types],
                    rule_version=ao.rule_version,
                    created_at=ao.created_at
                )
            )

        # 4. Load Active Solution Catalog entries
        cat_query = select(SolutionCatalogORM).where(SolutionCatalogORM.active == True)
        cat_result = await db.execute(cat_query)
        cat_orms = list(cat_result.scalars().all())

        active_catalog = []
        for co in cat_orms:
            active_catalog.append(
                SolutionCatalog(
                    id=co.id,
                    name=co.name,
                    solution_type=SolutionType(co.solution_type),
                    description=co.description,
                    supported_constraints=co.supported_constraints or [],
                    supported_industries=co.supported_industries or [],
                    minimum_applicability=co.minimum_applicability,
                    active=co.active,
                    created_at=co.created_at
                )
            )

        # 5. Clean existing recommended solutions for the session
        await self._cleanup_existing(db, session_id)

        # 6. Evaluate and persist matches
        now = datetime.now(timezone.utc)
        solution_orms = []
        serialized_results = []

        for app in applicabilities:
            constraint = constraints_map.get(app.constraint_id)
            if not constraint:
                continue

            for cat in active_catalog:
                rec_sol = SolutionRecommendationPolicy.evaluate(
                    profile_entity, constraint, app, cat
                )

                if rec_sol:
                    # Persist ORM model
                    sol_orm = RecommendedSolutionORM(
                        id=uuid4(),
                        session_id=session_id,
                        constraint_id=constraint.id,
                        solution_type=rec_sol.solution_type.value,
                        confidence=rec_sol.confidence,
                        priority_score=rec_sol.priority_score,
                        reasoning=rec_sol.reasoning,
                        evidence=[e.model_dump() for e in rec_sol.evidence],
                        created_at=now
                    )
                    db.add(sol_orm)
                    solution_orms.append(sol_orm)

                    serialized_results.append({
                        "id": str(sol_orm.id),
                        "session_id": str(session_id),
                        "constraint_id": str(constraint.id),
                        "solution_type": rec_sol.solution_type.value,
                        "confidence": rec_sol.confidence,
                        "priority_score": rec_sol.priority_score,
                        "reasoning": rec_sol.reasoning,
                        "evidence": [e.model_dump() for e in rec_sol.evidence],
                        "created_at": now.isoformat()
                    })

        await db.commit()
        logger.info(f"Persisted {len(solution_orms)} recommended solutions for session {session_id}.")

        # 7. Emit SOLUTIONS_RECOMMENDED event
        event = SolutionsRecommendedEvent(
            session_id=session_id,
            recommended_solutions=serialized_results,
            timestamp=now
        )
        await event_bus.publish(event)

        return solution_orms

    async def _cleanup_existing(self, db: AsyncSession, session_id: UUID):
        """Cleans up existing recommended solutions for a session to prevent duplicates."""
        await db.execute(delete(RecommendedSolutionORM).where(RecommendedSolutionORM.session_id == session_id))
        await db.commit()

# Event listener mapping APPLICABILITY_ANALYZED to Solution recommendation cascade
async def on_applicability_analyzed_listener(event: TviraDomainEvent):
    """Asynchronous subscriber caught on the Event Bus to run solution recommendation."""
    if event.event_type != "APPLICABILITY_ANALYZED":
        return

    logger.info(f"Solution Recommendation Engine subscriber intercepting APPLICABILITY_ANALYZED for session: {event.session_id}")
    
    async with SessionLocal() as db:
        try:
            engine = SolutionRecommendationEngine()
            await engine.evaluate_session_solutions(db, event.session_id)
        except Exception as e:
            logger.error(f"Async solution recommendation evaluation failed for session {event.session_id}: {e}")

def register_solution_listeners():
    """Binds event subscribers to the domain Event Bus."""
    event_bus.subscribe("APPLICABILITY_ANALYZED", on_applicability_analyzed_listener)
