from typing import Any, Dict, List, Union
from app.domain.entities.profile import BusinessProfile

class ConditionEvaluator:
    """Evaluates question template preconditions against a BusinessProfile instance.
    
    Example precondition format:
    {
      "and": [
        {"field": "business_type", "operator": "eq", "value": "Coaching Institute"},
        {"field": "team_size", "operator": "gt", "value": 5}
      ]
    }
    """
    def __init__(self, profile: BusinessProfile):
        self.profile = profile

    def evaluate(self, condition: Union[Dict[str, Any], List[Dict[str, Any]], None]) -> bool:
        """Entry point for checking eligibility conditions."""
        if not condition:
            return True

        if isinstance(condition, list):
            # Implicit 'and' for list of raw conditions
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

        # Resolve field value from profile
        if not hasattr(self.profile, field):
            return False

        profile_val = getattr(self.profile, field)

        if operator == "eq":
            return profile_val == target_val
        elif operator == "ne":
            return profile_val != target_val
        elif operator == "gt":
            if profile_val is None or target_val is None:
                return False
            return profile_val > target_val
        elif operator == "lt":
            if profile_val is None or target_val is None:
                return False
            return profile_val < target_val
        elif operator == "contains":
            if not isinstance(profile_val, list):
                return False
            return target_val in profile_val
        elif operator == "in":
            if not isinstance(target_val, list):
                return False
            return profile_val in target_val
        
        return False
