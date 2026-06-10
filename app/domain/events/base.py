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

class ConstraintsIdentifiedEvent(TviraDomainEvent):
    def __init__(self, session_id: UUID, business_profile_id: UUID, constraints: list, timestamp: datetime):
        super().__init__(
            event_type="CONSTRAINTS_IDENTIFIED",
            session_id=session_id,
            payload={
                "business_profile_id": str(business_profile_id),
                "constraints": constraints
            },
            timestamp=timestamp
        )

class ApplicabilityAnalyzedEvent(TviraDomainEvent):
    def __init__(self, session_id: UUID, applicability_results: list, timestamp: datetime):
        super().__init__(
            event_type="APPLICABILITY_ANALYZED",
            session_id=session_id,
            payload={
                "applicability_results": applicability_results
            },
            timestamp=timestamp
        )

class SolutionsRecommendedEvent(TviraDomainEvent):
    def __init__(self, session_id: UUID, recommended_solutions: list, timestamp: datetime):
        super().__init__(
            event_type="SOLUTIONS_RECOMMENDED",
            session_id=session_id,
            payload={
                "recommended_solutions": recommended_solutions
            },
            timestamp=timestamp
        )

class ReviewApprovedEvent(TviraDomainEvent):
    def __init__(self, session_id: UUID, review_id: UUID, recommendation_id: UUID, payload: dict, timestamp: datetime):
        super().__init__(
            event_type="REVIEW_APPROVED",
            session_id=session_id,
            payload={
                "review_id": str(review_id),
                "recommendation_id": str(recommendation_id),
                **payload
            },
            timestamp=timestamp
        )

class ReviewRejectedEvent(TviraDomainEvent):
    def __init__(self, session_id: UUID, review_id: UUID, recommendation_id: UUID, payload: dict, timestamp: datetime):
        super().__init__(
            event_type="REVIEW_REJECTED",
            session_id=session_id,
            payload={
                "review_id": str(review_id),
                "recommendation_id": str(recommendation_id),
                **payload
            },
            timestamp=timestamp
        )

class ReviewNeedsResearchEvent(TviraDomainEvent):
    def __init__(self, session_id: UUID, review_id: UUID, recommendation_id: UUID, payload: dict, timestamp: datetime):
        super().__init__(
            event_type="REVIEW_NEEDS_RESEARCH",
            session_id=session_id,
            payload={
                "review_id": str(review_id),
                "recommendation_id": str(recommendation_id),
                **payload
            },
            timestamp=timestamp
        )

class ReviewArchivedEvent(TviraDomainEvent):
    def __init__(self, session_id: UUID, review_id: UUID, recommendation_id: UUID, payload: dict, timestamp: datetime):
        super().__init__(
            event_type="REVIEW_ARCHIVED",
            session_id=session_id,
            payload={
                "review_id": str(review_id),
                "recommendation_id": str(recommendation_id),
                **payload
            },
            timestamp=timestamp
        )

class ReviewCompletedEvent(TviraDomainEvent):
    def __init__(self, session_id: UUID, review_session_id: UUID, reviewer: str, approved_count: int, timestamp: datetime):
        super().__init__(
            event_type="REVIEW_COMPLETED",
            session_id=session_id,
            payload={
                "review_session_id": str(review_session_id),
                "reviewer": reviewer,
                "approved_count": approved_count
            },
            timestamp=timestamp
        )



