from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.models.question import QuestionTemplateORM
from app.domain.entities.session import DiscoverySession
from app.domain.entities.profile import BusinessProfile
from app.domain.policies.eligibility import ConditionEvaluator

class QuestionService:
    """Service responsible for matching and ranking the next best question template."""

    async def get_next_question(
        self, db: AsyncSession, session: DiscoverySession, profile: BusinessProfile
    ) -> Optional[QuestionTemplateORM]:
        """Calculates and retrieves the next eligible question template.
        1. Fetch active templates applicable to the profile's industry or generic templates.
        2. Filter out already answered questions.
        3. Evaluate preconditions on remaining templates.
        4. Sort by priority (ascending) and return the first one.
        """
        # Fetch templates
        query = select(QuestionTemplateORM).where(
            QuestionTemplateORM.active == True
        )
        
        # Include templates matching the industry OR generic templates (industry is null or 'Generic')
        if profile.industry:
            query = query.where(
                or_(
                    QuestionTemplateORM.industry == profile.industry,
                    QuestionTemplateORM.industry == None,
                    QuestionTemplateORM.industry == "Generic"
                )
            )
        else:
            query = query.where(
                or_(
                    QuestionTemplateORM.industry == None,
                    QuestionTemplateORM.industry == "Generic"
                )
            )

        result = await db.execute(query)
        templates: List[QuestionTemplateORM] = list(result.scalars().all())

        # Filter out already answered keys
        unanswered_templates = [
            t for t in templates 
            if t.question_key not in session.progress_state.answered_keys
        ]

        # Evaluate preconditions
        evaluator = ConditionEvaluator(profile)
        eligible_templates = []
        
        for t in unanswered_templates:
            # Evaluate the JSON preconditions using our policy evaluator
            if evaluator.evaluate(t.preconditions):
                eligible_templates.append(t)

        if not eligible_templates:
            return None

        # Sort eligible templates: priority asc, then id for determinism
        eligible_templates.sort(key=lambda x: (x.priority, x.question_key))
        
        return eligible_templates[0]
