from enum import Enum

class LeadGrade(str, Enum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"

class RoutingPath(str, Enum):
    SELF_SERVE = "SELF_SERVE"
    CONSULTATION = "CONSULTATION"
    ENTERPRISE = "ENTERPRISE"

class PriorityQuadrant(str, Enum):
    QUICK_WINS = "Quick Wins"                     # High Impact, Low Complexity
    STRATEGIC_PROJECTS = "Strategic Projects"     # High Impact, High Complexity
    SECONDARY_FOCUS = "Secondary Focus"           # Low Impact, Low Complexity
    LONG_TERM_INITIATIVES = "Long-Term Initiatives" # Low Impact, High Complexity
