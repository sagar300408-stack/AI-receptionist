from enum import Enum

class LeadQualification(str, Enum):
    COLD = "COLD"
    WARM = "WARM"
    HOT = "HOT"

class LeadVolumeTier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class BusinessMaturity(str, Enum):
    STARTUP = "STARTUP"
    GROWTH = "GROWTH"
    MATURE = "MATURE"
