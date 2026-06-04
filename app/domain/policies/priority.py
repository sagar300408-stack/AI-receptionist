from typing import Dict, Any
from app.domain.value_objects.opportunity import Priority

class OpportunityPriorityPolicy:
    """Classifies computed scores into Priority categories based on scoring profile thresholds."""

    DEFAULT_THRESHOLDS = {
        "critical": {"impact": 80, "complexity": 40},
        "high": {"impact": 60, "complexity": 60},
        "medium": {"impact": 40, "complexity": 80}
    }

    @classmethod
    def resolve_priority(
        cls, impact_score: int, complexity_score: int, thresholds: Dict[str, Any] = None
    ) -> Priority:
        """Determines the Priority classification:
        - CRITICAL: Impact >= Critical.Impact and Complexity <= Critical.Complexity
        - HIGH: Impact >= High.Impact and Complexity <= High.Complexity
        - MEDIUM: Impact >= Medium.Impact and Complexity <= Medium.Complexity
        - LOW: Otherwise
        """
        th = thresholds or cls.DEFAULT_THRESHOLDS

        crit = th.get("critical", cls.DEFAULT_THRESHOLDS["critical"])
        high = th.get("high", cls.DEFAULT_THRESHOLDS["high"])
        med = th.get("medium", cls.DEFAULT_THRESHOLDS["medium"])

        if impact_score >= crit.get("impact", 80) and complexity_score <= crit.get("complexity", 40):
            return Priority.CRITICAL
        elif impact_score >= high.get("impact", 60) and complexity_score <= high.get("complexity", 60):
            return Priority.HIGH
        elif impact_score >= med.get("impact", 40) and complexity_score <= med.get("complexity", 80):
            return Priority.MEDIUM
        
        return Priority.LOW
