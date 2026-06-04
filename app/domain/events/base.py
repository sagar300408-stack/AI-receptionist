from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID
from pydantic import BaseModel, Field

class TviraDomainEvent(BaseModel):
    event_id: UUID = Field(default_factory=lambda: UUID(int=0)) # Will default to a unique UUID later, but keeping it serializable
    event_type: str
    session_id: UUID
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SessionCreatedEvent(TviraDomainEvent):
    def __init__(self, session_id: UUID, session_token: str):
        super().__init__(
            event_type="SESSION_CREATED",
            session_id=session_id,
            payload={"session_token": session_token}
        )

class ProfileUpdatedEvent(TviraDomainEvent):
    def __init__(self, session_id: UUID, updated_fields: Dict[str, Any], completion: float):
        super().__init__(
            event_type="PROFILE_UPDATED",
            session_id=session_id,
            payload={
                "updated_fields": updated_fields,
                "completion_percentage": completion
            }
        )

class DiscoveryCompletedEvent(TviraDomainEvent):
    def __init__(self, session_id: UUID, final_profile: Dict[str, Any]):
        super().__init__(
            event_type="DISCOVERY_COMPLETED",
            session_id=session_id,
            payload={"profile": final_profile}
        )

class ProfileGeneratedEvent(TviraDomainEvent):
    def __init__(self, session_id: UUID, profile: Dict[str, Any]):
        super().__init__(
            event_type="PROFILE_GENERATED",
            session_id=session_id,
            payload={"profile": profile}
        )

class LeadCapturedEvent(TviraDomainEvent):
    def __init__(self, session_id: UUID, name: str, email: str, phone: str):
        super().__init__(
            event_type="LEAD_CAPTURED",
            session_id=session_id,
            payload={"lead_name": name, "lead_email": email, "lead_phone": phone}
        )
