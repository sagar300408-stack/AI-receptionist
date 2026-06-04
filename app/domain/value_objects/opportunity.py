from enum import Enum

class Priority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class OpportunityCategory(str, Enum):
    COMMUNICATION = "Communication"
    LEAD_MANAGEMENT = "Lead Management"
    SALES = "Sales"
    CUSTOMER_SUPPORT = "Customer Support"
    OPERATIONS = "Operations"
    SCHEDULING = "Scheduling"
    REPORTING = "Reporting"
    AUTOMATION = "Automation"
    KNOWLEDGE_MANAGEMENT = "Knowledge Management"
