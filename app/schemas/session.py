from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

class SessionCreateRequest(BaseModel):
    business_name: Optional[str] = None

class ProgressStateSchema(BaseModel):
    answered_keys: List[str]
    pending_keys: List[str]
    current_key: Optional[str] = None

class SessionResponse(BaseModel):
    id: UUID
    session_token: str
    status: str
    progress_state: ProgressStateSchema
    expires_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class BusinessProfileSchema(BaseModel):
    id: UUID
    session_id: UUID
    industry: Optional[str] = None
    business_type: Optional[str] = None
    team_size: Optional[int] = None
    monthly_leads: Optional[int] = None
    monthly_customers: Optional[int] = None
    business_stage: Optional[str] = None
    communication_channels: List[str]
    pain_points: List[str]
    goals: List[str]
    profile_completion: float

    class Config:
        from_attributes = True

class SessionRespondRequest(BaseModel):
    question_key: str = Field(..., description="Key of the question template being answered")
    answer: str = Field(..., description="User raw text answer")

class SessionRespondResponse(BaseModel):
    session_id: UUID
    status: str
    profile_completion: float
    next_question_key: Optional[str] = None
    next_question_text: Optional[str] = None
    profile_preview: Dict[str, Any]

class LeadCaptureRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    email: str = Field(..., pattern=r"[^@]+@[^@]+\.[^@]+")
    phone: str = Field(..., min_length=5, max_length=50)

class SessionDetailsResponse(BaseModel):
    session: SessionResponse
    profile: BusinessProfileSchema
    derived_facts: Dict[str, Any] = Field(default_factory=dict)
