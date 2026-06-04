from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from app.domain.value_objects.status import SessionStatus
from app.core.exceptions import InvalidStateTransitionError

class ProgressState(BaseModel):
    answered_keys: List[str] = Field(default_factory=list)
    pending_keys: List[str] = Field(default_factory=list)
    current_key: Optional[str] = None

class DiscoverySession(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_token: str
    status: SessionStatus = SessionStatus.CREATED
    progress_state: ProgressState = Field(default_factory=ProgressState)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime

    def transition_to(self, new_status: SessionStatus):
        """Transitions state, raising an error if the path violates the status machine rules."""
        if not self.status.can_transition_to(new_status):
            raise InvalidStateTransitionError(self.status.value, new_status.value)
        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)

    def is_expired(self, current_time: datetime) -> bool:
        """Determines if the session has exceeded its expiration date."""
        t1 = current_time.replace(tzinfo=None) if current_time.tzinfo else current_time
        t2 = self.expires_at.replace(tzinfo=None) if self.expires_at.tzinfo else self.expires_at
        return t1 > t2

    def touch(self, expire_hours: int = 24):
        """Refreshes active timestamps and extends the session lifetime limit."""
        now = datetime.now(timezone.utc)
        self.updated_at = now
        # Avoid timezone issues by using timedelta
        from datetime import timedelta
        self.expires_at = now + timedelta(hours=expire_hours)

    def update_progress(self, answered_key: str, pending_keys: List[str], current_key: Optional[str]):
        """Modifies the dynamic traversal tracking list in real-time."""
        if answered_key not in self.progress_state.answered_keys:
            self.progress_state.answered_keys.append(answered_key)
        
        # Deduplicate and sync pending checklist keys
        self.progress_state.pending_keys = [
            k for k in pending_keys if k not in self.progress_state.answered_keys
        ]
        self.progress_state.current_key = current_key
        self.updated_at = datetime.now(timezone.utc)
