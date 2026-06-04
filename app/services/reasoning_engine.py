import re
from typing import Dict, Any, List, Optional
from app.domain.entities.profile import BusinessProfile
from app.domain.entities.evaluation import OpportunityEvidence

class ReasoningEngine:
    """Compiles explanation strings and extracts granular criteria validation traces."""

    @staticmethod
    def compile_reasoning(
        explanation_template: str,
        profile: BusinessProfile,
        context_facts: Dict[str, Any]
    ) -> str:
        """Formats templates (e.g., 'High inquiry volume ({monthly_leads}/mo)') with profile/context parameters."""
        if not explanation_template:
            return ""

        # Extract placeholder keys enclosed in brackets e.g. {monthly_leads}
        placeholders = re.findall(r"\{([^}]+)\}", explanation_template)
        kwargs = {}
        
        for key in placeholders:
            if hasattr(profile, key):
                val = getattr(profile, key)
                # Format list field to human-readable string
                if isinstance(val, list):
                    kwargs[key] = ", ".join(val) if val else "None"
                else:
                    kwargs[key] = str(val) if val is not None else "N/A"
            elif key in context_facts:
                kwargs[key] = str(context_facts[key])
            else:
                kwargs[key] = "N/A"

        try:
            return explanation_template.format(**kwargs)
        except Exception:
            return explanation_template

    @classmethod
    def extract_evidence_traces(
        cls,
        conditions: Dict[str, Any],
        profile: BusinessProfile,
        context_facts: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Walks condition structures recursively and extracts facts that triggered a match.
        Returns a list of dictionaries with field, value, operator, and rule_expression.
        """
        if not conditions:
            return []

        if "and" in conditions:
            traces = []
            for sub in conditions["and"]:
                traces.extend(cls.extract_evidence_traces(sub, profile, context_facts))
            return traces

        if "or" in conditions:
            traces = []
            for sub in conditions["or"]:
                traces.extend(cls.extract_evidence_traces(sub, profile, context_facts))
            return traces

        if "not" in conditions:
            return cls.extract_evidence_traces(conditions["not"], profile, context_facts)

        # Single condition
        field = conditions.get("field")
        operator = conditions.get("operator", "eq")
        target_val = conditions.get("value")

        if not field:
            return []

        # Find actual value
        actual_val = None
        if hasattr(profile, field):
            actual_val = getattr(profile, field)
        elif field in context_facts:
            actual_val = context_facts[field]

        rule_expr = f"{field} {operator} {target_val}"
        return [{
            "field": field,
            "value": actual_val,
            "operator": operator,
            "rule_expression": rule_expr
        }]
class ReasoningEngine:
    """Compiles explanation strings and extracts granular criteria validation traces."""

    @staticmethod
    def compile_reasoning(
        explanation_template: str,
        profile: BusinessProfile,
        context_facts: Dict[str, Any]
    ) -> str:
        """Formats templates (e.g., 'High inquiry volume ({monthly_leads}/mo)') with profile/context parameters."""
        if not explanation_template:
            return ""

        placeholders = re.findall(r"\{([^}]+)\}", explanation_template)
        kwargs = {}
        
        for key in placeholders:
            if hasattr(profile, key):
                val = getattr(profile, key)
                if isinstance(val, list):
                    kwargs[key] = ", ".join(val) if val else "None"
                else:
                    kwargs[key] = str(val) if val is not None else "N/A"
            elif key in context_facts:
                kwargs[key] = str(context_facts[key])
            else:
                kwargs[key] = "N/A"

        try:
            return explanation_template.format(**kwargs)
        except Exception:
            return explanation_template

    @classmethod
    def extract_evidence_traces(
        cls,
        conditions: Dict[str, Any],
        profile: BusinessProfile,
        context_facts: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Walks condition structures recursively and extracts facts that triggered a match."""
        if not conditions:
            return []

        if isinstance(conditions, list):
            traces = []
            for c in conditions:
                traces.extend(cls.extract_evidence_traces(c, profile, context_facts))
            return traces

        if "and" in conditions:
            traces = []
            for sub in conditions["and"]:
                traces.extend(cls.extract_evidence_traces(sub, profile, context_facts))
            return traces

        if "or" in conditions:
            traces = []
            for sub in conditions["or"]:
                traces.extend(cls.extract_evidence_traces(sub, profile, context_facts))
            return traces

        if "not" in conditions:
            return cls.extract_evidence_traces(conditions["not"], profile, context_facts)

        field = conditions.get("field")
        operator = conditions.get("operator", "eq")
        target_val = conditions.get("value")

        if not field:
            return []

        actual_val = None
        if hasattr(profile, field):
            actual_val = getattr(profile, field)
        elif field in context_facts:
            actual_val = context_facts[field]

        rule_expr = f"{field} {operator} {target_val}"
        return [{
            "field": field,
            "value": actual_val,
            "operator": operator,
            "rule_expression": rule_expr
        }]
