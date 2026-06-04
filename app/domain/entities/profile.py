from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field

class BusinessProfile(BaseModel):
    id: Optional[UUID] = None
    session_id: UUID
    industry: Optional[str] = None
    business_type: Optional[str] = None
    team_size: Optional[int] = None
    monthly_leads: Optional[int] = None
    monthly_customers: Optional[int] = None
    business_stage: Optional[str] = None
    communication_channels: List[str] = Field(default_factory=list)
    pain_points: List[str] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)
    profile_completion: float = 0.0

    def calculate_completion(self) -> float:
        """Calculates completion percentage of the profile based on required fields.
        Required core fields: industry, business_type, team_size, monthly_leads, 
        monthly_customers, business_stage, communication_channels, pain_points, goals.
        """
        core_fields = [
            self.industry,
            self.business_type,
            self.team_size,
            self.monthly_leads,
            self.monthly_customers,
            self.business_stage
        ]
        
        # Calculate filled count for scalar fields
        filled_count = sum(1 for field in core_fields if field is not None)
        
        # Add list fields if they have items
        if self.communication_channels:
            filled_count += 1
        if self.pain_points:
            filled_count += 1
        if self.goals:
            filled_count += 1
            
        total_fields = len(core_fields) + 3 # 6 scalars + 3 lists
        self.profile_completion = round((filled_count / total_fields) * 100.0, 2)
        return self.profile_completion

    def update_field(self, key: str, value: any):
        """Safely updates fields and recalculates completion rates."""
        if hasattr(self, key):
            # Special parsing logic for inputs
            if key in ["communication_channels", "pain_points", "goals"]:
                if isinstance(value, list):
                    setattr(self, key, value)
                elif isinstance(value, str):
                    # Append if it's a single value or parse comma-separated
                    current = getattr(self, key)
                    parts = [p.strip() for p in value.split(",") if p.strip()]
                    for p in parts:
                        if p not in current:
                            current.append(p)
                    setattr(self, key, current)
            else:
                if key in ["team_size", "monthly_leads", "monthly_customers"]:
                    try:
                        # Extract digit if user writes "10-20 leads" or similar
                        if isinstance(value, str):
                            digits = "".join(filter(str.isdigit, value))
                            setattr(self, key, int(digits) if digits else 0)
                        else:
                            setattr(self, key, int(value))
                    except (ValueError, TypeError):
                        setattr(self, key, 0)
                else:
                    setattr(self, key, value)
            
            self.calculate_completion()
