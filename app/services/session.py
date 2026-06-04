import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.core.config import settings
from app.core.exceptions import SessionNotFoundError, QuestionEligibilityError
from app.domain.entities.session import DiscoverySession, ProgressState
from app.domain.entities.profile import BusinessProfile
from app.domain.value_objects.status import SessionStatus
from app.domain.events.base import (
    SessionCreatedEvent, DiscoveryCompletedEvent, ProfileGeneratedEvent, LeadCapturedEvent
)
from app.models.session import SessionORM
from app.models.profile import BusinessProfileORM
from app.models.response import UserResponseORM
from app.models.context import BusinessContextORM
from app.services.event_bus import event_bus
from app.services.blueprint import BlueprintService
from app.services.question import QuestionService
from app.services.discovery import DiscoveryService

logger = logging.getLogger("tvira.session_service")

class SessionService:
    """Service orchestrating the complete discovery session database lifecycle."""

    def __init__(self):
        self.blueprint_service = BlueprintService()
        self.question_service = QuestionService()
        self.discovery_service = DiscoveryService()

    def _to_session_entity(self, orm: SessionORM) -> DiscoverySession:
        return DiscoverySession(
            id=orm.id,
            session_token=orm.session_token,
            status=SessionStatus(orm.status),
            progress_state=ProgressState(
                answered_keys=orm.progress_state.get("answered_keys", []),
                pending_keys=orm.progress_state.get("pending_keys", []),
                current_key=orm.progress_state.get("current_key")
            ),
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            expires_at=orm.expires_at
        )

    def _to_profile_entity(self, orm: BusinessProfileORM) -> BusinessProfile:
        return BusinessProfile(
            id=orm.id,
            session_id=orm.session_id,
            industry=orm.industry,
            business_type=orm.business_type,
            team_size=orm.team_size,
            monthly_leads=orm.monthly_leads,
            monthly_customers=orm.monthly_customers,
            business_stage=orm.business_stage,
            communication_channels=orm.communication_channels or [],
            pain_points=orm.pain_points or [],
            goals=orm.goals or [],
            profile_completion=orm.profile_completion
        )

    async def create_session(self, db: AsyncSession, business_name: Optional[str] = None) -> Tuple[DiscoverySession, BusinessProfile]:
        """Creates and persists a new discovery session and empty profile."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=settings.SESSION_EXPIRE_HOURS)
        token = f"tvr_{uuid4().hex}"

        # Initialize domain entities
        session_entity = DiscoverySession(
            session_token=token,
            expires_at=expires_at
        )
        profile_entity = BusinessProfile(
            session_id=session_entity.id
        )

        # Map to ORM models
        session_orm = SessionORM(
            id=session_entity.id,
            session_token=session_entity.session_token,
            status=session_entity.status.value,
            progress_state={
                "answered_keys": session_entity.progress_state.answered_keys,
                "pending_keys": session_entity.progress_state.pending_keys,
                "current_key": session_entity.progress_state.current_key
            },
            expires_at=session_entity.expires_at,
            created_at=session_entity.created_at,
            updated_at=session_entity.updated_at
        )

        profile_orm = BusinessProfileORM(
            id=profile_entity.id or uuid4(),
            session_id=profile_entity.session_id,
            industry=profile_entity.industry,
            business_type=profile_entity.business_type,
            team_size=profile_entity.team_size,
            monthly_leads=profile_entity.monthly_leads,
            monthly_customers=profile_entity.monthly_customers,
            business_stage=profile_entity.business_stage,
            communication_channels=profile_entity.communication_channels,
            pain_points=profile_entity.pain_points,
            goals=profile_entity.goals,
            profile_completion=profile_entity.profile_completion,
            created_at=now,
            updated_at=now
        )

        db.add(session_orm)
        db.add(profile_orm)
        await db.commit()
        await db.refresh(session_orm)
        await db.refresh(profile_orm)

        logger.info(f"Created session ORM: {session_orm.id} with token: {token}")

        # Publish Event
        await event_bus.publish(SessionCreatedEvent(session_entity.id, token))

        return session_entity, profile_entity

    async def get_session_by_token(self, db: AsyncSession, token: str) -> Tuple[DiscoverySession, BusinessProfile]:
        """Resolves a session and profile by session token."""
        s_query = select(SessionORM).where(SessionORM.session_token == token)
        s_result = await db.execute(s_query)
        session_orm = s_result.scalars().first()
        if not session_orm:
            raise SessionNotFoundError(token)

        p_query = select(BusinessProfileORM).where(BusinessProfileORM.session_id == session_orm.id)
        p_result = await db.execute(p_query)
        profile_orm = p_result.scalars().first()

        # Convert to entities
        session = self._to_session_entity(session_orm)
        profile = self._to_profile_entity(profile_orm)
        return session, profile

    async def get_session_by_id(self, db: AsyncSession, session_id: UUID) -> Tuple[DiscoverySession, BusinessProfile]:
        """Resolves a session and profile by explicit UUID."""
        session_orm = await db.get(SessionORM, session_id)
        if not session_orm:
            raise SessionNotFoundError(str(session_id))

        p_query = select(BusinessProfileORM).where(BusinessProfileORM.session_id == session_id)
        p_result = await db.execute(p_query)
        profile_orm = p_result.scalars().first()

        session = self._to_session_entity(session_orm)
        profile = self._to_profile_entity(profile_orm)
        return session, profile

    async def respond_to_question(
        self, db: AsyncSession, session_id: UUID, question_key: str, raw_answer: str
    ) -> Tuple[DiscoverySession, BusinessProfile, Optional[str]]:
        """Handles a user response, updates profile, maps next question, and persists progress."""
        session_orm = await db.get(SessionORM, session_id)
        if not session_orm:
            raise SessionNotFoundError(str(session_id))

        p_query = select(BusinessProfileORM).where(BusinessProfileORM.session_id == session_id)
        p_result = await db.execute(p_query)
        profile_orm = p_result.scalars().first()

        # Check expiration
        session = self._to_session_entity(session_orm)
        profile = self._to_profile_entity(profile_orm)
        now = datetime.now(timezone.utc)
        if session.is_expired(now):
            session.transition_to(SessionStatus.EXPIRED)
            session_orm.status = session.status.value
            await db.commit()
            return session, profile, None

        # Validate transition to IN_PROGRESS if still in CREATED
        if session.status == SessionStatus.CREATED:
            session.transition_to(SessionStatus.DISCOVERY_IN_PROGRESS)
            session_orm.status = session.status.value

        # Apply response logic to profile
        parsed_data = await self.discovery_service.apply_response_to_profile(
            db, profile, question_key, raw_answer
        )

        # Log User Response into audit log
        response_orm = UserResponseORM(
            id=uuid4(),
            session_id=session_id,
            question_key=question_key,
            question_text="", # Will load text dynamically or leave blank for simplicity
            raw_answer=raw_answer,
            parsed_data=parsed_data,
            created_at=now
        )
        db.add(response_orm)

        # Refresh expiration window
        session.touch(settings.SESSION_EXPIRE_HOURS)

        # Append current question to answered keys before calculating next question
        if question_key not in session.progress_state.answered_keys:
            session.progress_state.answered_keys.append(question_key)

        # Fetch next eligible question
        next_question_template = await self.question_service.get_next_question(db, session, profile)
        
        next_key = next_question_template.question_key if next_question_template else None
        
        # Determine remaining pending keys (mock list or fetch all unanswered keys)
        pending_keys = []
        if next_key:
            pending_keys.append(next_key)

        # Update progression context on session entity
        session.update_progress(question_key, pending_keys, next_key)

        # Sync entities back to ORM
        session_orm.status = session.status.value
        session_orm.progress_state = {
            "answered_keys": session.progress_state.answered_keys,
            "pending_keys": session.progress_state.pending_keys,
            "current_key": session.progress_state.current_key
        }
        session_orm.expires_at = session.expires_at
        session_orm.updated_at = session.updated_at

        # Sync profile changes to ORM
        profile_orm.industry = profile.industry
        profile_orm.business_type = profile.business_type
        profile_orm.team_size = profile.team_size
        profile_orm.monthly_leads = profile.monthly_leads
        profile_orm.monthly_customers = profile.monthly_customers
        profile_orm.business_stage = profile.business_stage
        profile_orm.communication_channels = profile.communication_channels
        profile_orm.pain_points = profile.pain_points
        profile_orm.goals = profile.goals
        profile_orm.profile_completion = profile.profile_completion
        profile_orm.updated_at = now

        await db.commit()
        await db.refresh(session_orm)
        await db.refresh(profile_orm)

        next_text = next_question_template.question_text if next_question_template else None
        return session, profile, next_text

    async def complete_session(self, db: AsyncSession, session_id: UUID) -> Tuple[DiscoverySession, BusinessProfile]:
        """Finalizes discovery session, computes Derived Context Facts, and saves them."""
        session_orm = await db.get(SessionORM, session_id)
        if not session_orm:
            raise SessionNotFoundError(str(session_id))

        p_query = select(BusinessProfileORM).where(BusinessProfileORM.session_id == session_id)
        p_result = await db.execute(p_query)
        profile_orm = p_result.scalars().first()

        session = self._to_session_entity(session_orm)
        profile = self._to_profile_entity(profile_orm)

        # State transition chain: IN_PROGRESS -> COMPLETED -> GENERATED
        session.transition_to(SessionStatus.DISCOVERY_COMPLETED)
        session_orm.status = session.status.value
        await db.commit()

        # Run derived Business Context evaluation (v1 facts)
        facts = self.discovery_service.evaluate_business_context_facts(profile)
        now = datetime.now(timezone.utc)
        
        context_orm = BusinessContextORM(
            id=uuid4(),
            session_id=session_id,
            context_version="v1",
            generated_by="DiscoveryFactEngine",
            facts=facts,
            created_at=now,
            updated_at=now
        )
        db.add(context_orm)

        # Transition profile: COMPLETED -> PROFILE_GENERATED
        session.transition_to(SessionStatus.PROFILE_GENERATED)
        session_orm.status = session.status.value
        
        await db.commit()
        await db.refresh(session_orm)

        # Publish Events
        await event_bus.publish(DiscoveryCompletedEvent(session_id, profile.model_dump(mode="json")))
        await event_bus.publish(ProfileGeneratedEvent(session_id, profile.model_dump(mode="json")))

        return session, profile

    async def capture_lead(self, db: AsyncSession, session_id: UUID, name: str, email: str, phone: str) -> DiscoverySession:
        """Captures lead details and updates status to LEAD_CAPTURED."""
        session_orm = await db.get(SessionORM, session_id)
        if not session_orm:
            raise SessionNotFoundError(str(session_id))

        session = self._to_session_entity(session_orm)
        
        # State transition: PROFILE_GENERATED -> READY_FOR_ANALYSIS -> ANALYZED -> REPORT_GENERATED -> LEAD_CAPTURED
        # For simplicity, we step through these in sequence to honor the transition policy constraints
        transitions = [
            SessionStatus.READY_FOR_ANALYSIS,
            SessionStatus.ANALYZED,
            SessionStatus.REPORT_GENERATED,
            SessionStatus.LEAD_CAPTURED
        ]
        
        for next_status in transitions:
            session.transition_to(next_status)
            session_orm.status = session.status.value

        session_orm.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(session_orm)

        # Publish lead capture event
        await event_bus.publish(LeadCapturedEvent(session_id, name, email, phone))

        return session
