from typing import Any, Dict, List, Union, Optional
from app.domain.entities.profile import BusinessProfile

class ConditionEvaluator:
    """Evaluates question template preconditions and opportunity rules against 
    a BusinessProfile instance and optional BusinessContext facts.
    """
    def __init__(self, profile: BusinessProfile, context_facts: Optional[Dict[str, Any]] = None):
        self.profile = profile
        self.context_facts = context_facts or {}

    def evaluate(self, condition: Union[Dict[str, Any], List[Dict[str, Any]], None]) -> bool:
        """Entry point for checking eligibility conditions."""
        if not condition:
            return True

        if isinstance(condition, list):
            return all(self._evaluate_single(c) for c in condition)

        if "and" in condition:
            return all(self.evaluate(sub_cond) for sub_cond in condition["and"])

        if "or" in condition:
            return any(self.evaluate(sub_cond) for sub_cond in condition["or"])

        if "not" in condition:
            return not self.evaluate(condition["not"])

        return self._evaluate_single(condition)

    def _evaluate_single(self, cond: Dict[str, Any]) -> bool:
        field = cond.get("field")
        operator = cond.get("operator", "eq")
        target_val = cond.get("value")

        if not field:
            return True

        # Resolve field value from profile or context facts
        resolved = False
        val = None

        if hasattr(self.profile, field):
            val = getattr(self.profile, field)
            resolved = True
        elif field in self.context_facts:
            val = self.context_facts[field]
            resolved = True

        if not resolved:
            return False

        if operator == "eq":
            return val == target_val
        elif operator == "ne":
            return val != target_val
        elif operator == "gt":
            if val is None or target_val is None:
                return False
            return val > target_val
        elif operator == "gte":
            if val is None or target_val is None:
                return False
            return val >= target_val
        elif operator == "lt":
            if val is None or target_val is None:
                return False
            return val < target_val
        elif operator == "lte":
            if val is None or target_val is None:
                return False
            return val <= target_val
        elif operator == "contains":
            if not isinstance(val, list):
                return False
            return target_val in val
        elif operator == "in":
            if not isinstance(target_val, list):
                return False
            return val in target_val
        
        return False
