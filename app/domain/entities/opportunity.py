from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from app.domain.value_objects.opportunity import OpportunityCategory

class OpportunityGroup(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    category: OpportunityCategory
    description: Optional[str] = None
    active: bool = True

class OpportunityTemplate(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    group_id: Optional[UUID] = None
    code: str
    name: str
    version: str = "v1"
    description: Optional[str] = None
    base_impact: float = 50.0
    base_complexity: float = 50.0
    active: bool = True
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def is_currently_active(self, current_time: datetime) -> bool:
        """Verifies if the template is active and within its effective lifecycle date boundaries."""
        if not self.active:
            return False
        if self.effective_from and current_time < self.effective_from:
            return False
        if self.effective_to and current_time > self.effective_to:
            return False
        return True

class OpportunityRule(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    template_id: UUID
    rule_type: str # ELIGIBILITY, IMPACT_MODIFIER, COMPLEXITY_MODIFIER, REASONING
    conditions: Dict[str, Any]
    modifier_value: Optional[float] = None
    explanation_template: Optional[str] = None
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
