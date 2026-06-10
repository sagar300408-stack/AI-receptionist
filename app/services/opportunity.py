import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import Dict, Any, List, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import SessionLocal
from app.core.exceptions import SessionNotFoundError
from app.domain.entities.profile import BusinessProfile
from app.domain.entities.evaluation import OpportunityEvaluation, OpportunityResult, OpportunityEvidence
from app.domain.policies.scoring import OpportunityScoringPolicy
from app.domain.policies.priority import OpportunityPriorityPolicy
from app.domain.events.base import TviraDomainEvent
from app.models.session import SessionORM
from app.models.profile import BusinessProfileORM
from app.models.context import BusinessContextORM
from app.models.opportunity import (
    OpportunityTemplateORM, OpportunityRuleORM, ScoringProfileORM,
    OpportunityEvaluationORM, OpportunityResultORM, OpportunityEvidenceORM,
    OpportunityGroupORM
)
from app.services.event_bus import event_bus
from app.services.rules_evaluator import RulesEvaluator
from app.services.reasoning_engine import ReasoningEngine

logger = logging.getLogger("tvira.opportunity_service")

# Custom domain events for Segment 2
class OpportunitiesGeneratedEvent(TviraDomainEvent):
    def __init__(self, session_id: UUID, evaluation_id: UUID, results: List[Dict[str, Any]]):
        super().__init__(
            event_type="OPPORTUNITIES_GENERATED",
            session_id=session_id,
            payload={"evaluation_id": str(evaluation_id), "opportunities": results}
        )

class OpportunityEvaluatedEvent(TviraDomainEvent):
    def __init__(self, session_id: UUID, template_code: str, priority: str, scores: Dict[str, int]):
        super().__init__(
            event_type="OPPORTUNITY_EVALUATED",
            session_id=session_id,
            payload={"template_code": template_code, "priority": priority, "scores": scores}
        )

class OpportunityEngine:
    """Core coordinator executing Segment 2 evaluation rules and persisting results."""

    async def evaluate_session_opportunities(self, db: AsyncSession, session_id: UUID) -> OpportunityEvaluationORM:
        """Loads session metrics, runs eligibility filters, computes scores, and saves evaluations."""
        logger.info(f"Initiating Opportunity evaluation for session {session_id}...")

        # 1. Fetch Session & Profile
        session_orm = await db.get(SessionORM, session_id)
        if not session_orm:
            raise SessionNotFoundError(str(session_id))

        p_query = select(BusinessProfileORM).where(BusinessProfileORM.session_id == session_id)
        p_result = await db.execute(p_query)
        profile_orm = p_result.scalars().first()

        # Map to domain entities
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

        # 2. Fetch Derived Business Context facts
        c_query = select(BusinessContextORM).where(BusinessContextORM.session_id == session_id)
        c_result = await db.execute(c_query)
        context_orm = c_result.scalars().first()
        context_facts = context_orm.facts if context_orm else {}

        # Fetch Constraints for this session to populate context_facts
        from app.models.constraint import ConstraintORM
        const_query = select(ConstraintORM).where(ConstraintORM.session_id == session_id)
        const_result = await db.execute(const_query)
        constraints = list(const_result.scalars().all())

        for c in constraints:
            context_facts[c.category] = True
            context_facts[f"{c.category}_severity"] = c.severity
            context_facts[f"{c.category}_confidence"] = c.confidence
            context_facts[f"{c.category}_impact"] = c.impact_score

        # Fetch AI Applicability for this session to populate context_facts
        from app.models.applicability import AIApplicabilityORM
        app_query = select(AIApplicabilityORM).where(AIApplicabilityORM.session_id == session_id)
        app_result = await db.execute(app_query)
        applicabilities = list(app_result.scalars().all())

        constraint_id_map = {c.id: c.category for c in constraints}
        for a in applicabilities:
            c_cat = constraint_id_map.get(a.constraint_id)
            if c_cat:
                context_facts[f"{c_cat}_applicability"] = a.category
                context_facts[f"{c_cat}_applicability_score"] = a.applicability_score
                context_facts[f"{c_cat}_applicability_confidence"] = a.confidence

        # Fetch APPROVED Recommended Solutions and their Founder Review details to populate context_facts
        from app.models.solution import RecommendedSolutionORM
        from app.models.review import FounderReviewORM
        sol_query = select(RecommendedSolutionORM, FounderReviewORM).join(
            FounderReviewORM, RecommendedSolutionORM.id == FounderReviewORM.recommendation_id
        ).where(
            RecommendedSolutionORM.session_id == session_id,
            FounderReviewORM.review_status == "APPROVED"
        )
        sol_result = await db.execute(sol_query)
        solutions_rows = list(sol_result.all())

        for s_orm, r_orm in solutions_rows:
            context_facts[s_orm.solution_type] = True
            p_score = r_orm.priority_score if r_orm.priority_score is not None else s_orm.priority_score
            context_facts[f"{s_orm.solution_type}_priority"] = p_score
            context_facts[f"{s_orm.solution_type}_confidence"] = s_orm.confidence
            context_facts[f"{s_orm.solution_type}_reasoning"] = s_orm.reasoning

        # 3. Load Active Scoring Profile
        sp_query = select(ScoringProfileORM).where(ScoringProfileORM.active == True)
        sp_result = await db.execute(sp_query)
        scoring_profile = sp_result.scalars().first()
        thresholds = scoring_profile.thresholds if scoring_profile else None
        scoring_profile_id = scoring_profile.id if scoring_profile else None

        # 4. Fetch All Active Templates
        now = datetime.now(timezone.utc)
        templates_query = select(OpportunityTemplateORM).where(OpportunityTemplateORM.active == True)
        templates_result = await db.execute(templates_query)
        templates = list(templates_result.scalars().all())

        # Filter lifecycle range in memory (SQLite datetime issues handled safely)
        active_templates = []
        for t in templates:
            # Safe date comparison
            from_ok = True
            to_ok = True
            if t.effective_from:
                from_ok = now.replace(tzinfo=None) >= t.effective_from.replace(tzinfo=None)
            if t.effective_to:
                to_ok = now.replace(tzinfo=None) <= t.effective_to.replace(tzinfo=None)
            if from_ok and to_ok:
                active_templates.append(t)

        # 5. Fetch Rules mapped to active templates
        template_ids = [t.id for t in active_templates]
        rules_list: List[OpportunityRuleORM] = []
        if template_ids:
            rules_query = select(OpportunityRuleORM).where(
                OpportunityRuleORM.template_id.in_(template_ids),
                OpportunityRuleORM.active == True
            )
            rules_result = await db.execute(rules_query)
            rules_list = list(rules_result.scalars().all())

        # Group rules by template_id
        rules_by_template: Dict[UUID, List[OpportunityRuleORM]] = {}
        for r in rules_list:
            if r.template_id not in rules_by_template:
                rules_by_template[r.template_id] = []
            rules_by_template[r.template_id].append(r)

        # 6. Initialize Evaluation Batch log
        evaluation_orm = OpportunityEvaluationORM(
            id=uuid4(),
            session_id=session_id,
            scoring_profile_id=scoring_profile_id,
            evaluated_at=now,
            engine_version="1.0",
            ruleset_version="2026.06.04"
        )
        db.add(evaluation_orm)

        results_to_emit = []

        # 7. Evaluate Opportunities
        for template in active_templates:
            t_rules = rules_by_template.get(template.id, [])
            
            # Divide rules by type
            eligibility_rules = [r for r in t_rules if r.rule_type == "ELIGIBILITY"]
            scoring_rules = [r for r in t_rules if r.rule_type in ["IMPACT_MODIFIER", "COMPLEXITY_MODIFIER"]]
            reasoning_rules = [r for r in t_rules if r.rule_type == "REASONING"]

            # Evaluate Eligibility
            eligible = True
            for rule in eligibility_rules:
                if not RulesEvaluator.evaluate_rule(rule.conditions, profile_entity, context_facts):
                    eligible = False
                    break

            if not eligible:
                continue

            # Evaluate Scoring modifiers
            matched_scoring_rules = []
            for rule in scoring_rules:
                if RulesEvaluator.evaluate_rule(rule.conditions, profile_entity, context_facts):
                    matched_scoring_rules.append(rule)

            # Compute Scores
            impact, complexity, confidence = OpportunityScoringPolicy.calculate_scores(
                template, matched_scoring_rules, profile_entity
            )

            # Resolve Priority Tier
            priority = OpportunityPriorityPolicy.resolve_priority(impact, complexity, thresholds)

            # Evaluate Reasoning modifiers & extract evidence
            compiled_reasons = []
            evidence_records = []

            for rule in reasoning_rules:
                if RulesEvaluator.evaluate_rule(rule.conditions, profile_entity, context_facts):
                    reason = ReasoningEngine.compile_reasoning(rule.explanation_template, profile_entity, context_facts)
                    if reason:
                        compiled_reasons.append(reason)
                    
                    # Extract granular matching evidence
                    traces = ReasoningEngine.extract_evidence_traces(rule.conditions, profile_entity, context_facts)
                    for trace in traces:
                        evidence_records.append(trace)

            # Persist Opportunity Result record
            result_orm = OpportunityResultORM(
                id=uuid4(),
                evaluation_id=evaluation_orm.id,
                template_id=template.id,
                priority=priority.value,
                confidence=confidence,
                impact_score=impact,
                complexity_score=complexity,
                reasoning=compiled_reasons,
                created_at=now
            )
            db.add(result_orm)

            # Persist Evidence records
            for ev in evidence_records:
                evidence_orm = OpportunityEvidenceORM(
                    id=uuid4(),
                    result_id=result_orm.id,
                    field=ev["field"],
                    value=ev["value"],
                    operator=ev["operator"],
                    rule_expression=ev["rule_expression"],
                    created_at=now
                )
                db.add(evidence_orm)

            results_to_emit.append({
                "template_code": template.code,
                "priority": priority.value,
                "impact": impact,
                "complexity": complexity,
                "confidence": confidence,
                "reasoning": compiled_reasons
            })

            # Publish single item event
            await event_bus.publish(OpportunityEvaluatedEvent(
                session_id=session_id,
                template_code=template.code,
                priority=priority.value,
                scores={"impact": impact, "complexity": complexity}
            ))

        await db.commit()
        await db.refresh(evaluation_orm)

        logger.info(f"Saved opportunity evaluation {evaluation_orm.id} for session {session_id}.")

        # Publish global evaluation event
        await event_bus.publish(OpportunitiesGeneratedEvent(
            session_id=session_id,
            evaluation_id=evaluation_orm.id,
            results=results_to_emit
        ))

        return evaluation_orm

# Event listener mapping REVIEW_COMPLETED to Segment 2
async def on_review_completed_listener(event: TviraDomainEvent):
    """Asynchronous subscriber caught on the Event Bus to decouple logic runs."""
    if event.event_type != "REVIEW_COMPLETED":
        return

    logger.info(f"Event subscriber intercepting REVIEW_COMPLETED event for session: {event.session_id}")
    
    # Instantiate async db connection
    async with SessionLocal() as db:
        try:
            engine = OpportunityEngine()
            await engine.evaluate_session_opportunities(db, event.session_id)
        except Exception as e:
            logger.error(f"Async opportunity calculation failed on REVIEW_COMPLETED for session {event.session_id}: {e}")

def register_opportunity_listeners():
    """Binds event subscribers to the domain Event Bus."""
    event_bus.subscribe("REVIEW_COMPLETED", on_review_completed_listener)

