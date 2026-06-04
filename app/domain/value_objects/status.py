from enum import Enum

class SessionStatus(str, Enum):
    CREATED = "CREATED"
    DISCOVERY_IN_PROGRESS = "DISCOVERY_IN_PROGRESS"
    DISCOVERY_COMPLETED = "DISCOVERY_COMPLETED"
    PROFILE_GENERATED = "PROFILE_GENERATED"
    READY_FOR_ANALYSIS = "READY_FOR_ANALYSIS"
    ANALYZED = "ANALYZED"
    REPORT_GENERATED = "REPORT_GENERATED"
    LEAD_CAPTURED = "LEAD_CAPTURED"
    ARCHIVED = "ARCHIVED"
    EXPIRED = "EXPIRED"

    @classmethod
    def get_valid_transitions(cls) -> dict:
        return {
            cls.CREATED: {cls.DISCOVERY_IN_PROGRESS, cls.EXPIRED},
            cls.DISCOVERY_IN_PROGRESS: {cls.DISCOVERY_IN_PROGRESS, cls.DISCOVERY_COMPLETED, cls.EXPIRED},
            cls.DISCOVERY_COMPLETED: {cls.PROFILE_GENERATED, cls.EXPIRED},
            cls.PROFILE_GENERATED: {cls.READY_FOR_ANALYSIS, cls.EXPIRED},
            cls.READY_FOR_ANALYSIS: {cls.ANALYZED, cls.EXPIRED},
            cls.ANALYZED: {cls.REPORT_GENERATED, cls.EXPIRED},
            cls.REPORT_GENERATED: {cls.LEAD_CAPTURED, cls.EXPIRED},
            cls.LEAD_CAPTURED: {cls.ARCHIVED, cls.EXPIRED},
            cls.ARCHIVED: set(),
            cls.EXPIRED: set()
        }

    def can_transition_to(self, target: "SessionStatus") -> bool:
        valid_targets = self.get_valid_transitions().get(self, set())
        return target in valid_targets
