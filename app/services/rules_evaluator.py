from typing import Dict, Any, Optional
from app.domain.policies.eligibility import ConditionEvaluator
from app.domain.entities.profile import BusinessProfile

class RulesEvaluator:
    """Service layer wrapper around the domain ConditionEvaluator policy."""

    @staticmethod
    def evaluate_rule(
        conditions: Dict[str, Any],
        profile: BusinessProfile,
        context_facts: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Returns True if the profile and context facts satisfy the given rules conditions."""
        evaluator = ConditionEvaluator(profile, context_facts)
        return evaluator.evaluate(conditions)
