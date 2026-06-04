from uuid import UUID
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_session_service
from app.core.database import get_db_session
from app.core.exceptions import TviraException, SessionNotFoundError, InvalidStateTransitionError
from app.schemas.session import (
    SessionCreateRequest, SessionResponse, SessionRespondRequest, 
    SessionRespondResponse, LeadCaptureRequest, SessionDetailsResponse,
    ProgressStateSchema, BusinessProfileSchema
)
from app.services.session import SessionService
from app.models.context import BusinessContextORM
from sqlalchemy import select

router = APIRouter()

@router.post("", response_model=SessionRespondResponse, status_code=status.HTTP_201_CREATED)
async def start_discovery_session(
    payload: SessionCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    service: SessionService = Depends(get_session_service)
):
    """Initializes a new business discovery session and fetches the first question."""
    try:
        session, profile = await service.create_session(db, payload.business_name)
        
        # Calculate first question
        next_question_template = await service.question_service.get_next_question(db, session, profile)
        
        return SessionRespondResponse(
            session_id=session.id,
            status=session.status.value,
            profile_completion=profile.profile_completion,
            next_question_key=next_question_template.question_key if next_question_template else None,
            next_question_text=next_question_template.question_text if next_question_template else "Let's complete the profile setup.",
            profile_preview=profile.model_dump(exclude={"id", "session_id"})
        )
    except TviraException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/resume/{token}", response_model=SessionDetailsResponse)
async def resume_discovery_session(
    token: str,
    db: AsyncSession = Depends(get_db_session),
    service: SessionService = Depends(get_session_service)
):
    """Resumes an existing session by token, returning state and profile."""
    try:
        session, profile = await service.get_session_by_token(db, token)
        
        # Load derived context if present
        c_query = select(BusinessContextORM).where(BusinessContextORM.session_id == session.id)
        c_result = await db.execute(c_query)
        context_orm = c_result.scalars().first()
        facts = context_orm.facts if context_orm else {}

        return SessionDetailsResponse(
            session=SessionResponse.model_validate(session),
            profile=BusinessProfileSchema.model_validate(profile),
            derived_facts=facts
        )
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except TviraException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{session_id}", response_model=SessionDetailsResponse)
async def get_session_status(
    session_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    service: SessionService = Depends(get_session_service)
):
    """Retrieves session logs and details by UUID."""
    try:
        session, profile = await service.get_session_by_id(db, session_id)
        
        c_query = select(BusinessContextORM).where(BusinessContextORM.session_id == session_id)
        c_result = await db.execute(c_query)
        context_orm = c_result.scalars().first()
        facts = context_orm.facts if context_orm else {}

        return SessionDetailsResponse(
            session=SessionResponse.model_validate(session),
            profile=BusinessProfileSchema.model_validate(profile),
            derived_facts=facts
        )
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except TviraException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{session_id}/respond", response_model=SessionRespondResponse)
async def submit_response(
    session_id: UUID,
    payload: SessionRespondRequest,
    db: AsyncSession = Depends(get_db_session),
    service: SessionService = Depends(get_session_service)
):
    """Submits the answer to the current question, parses data, and resolves the next step."""
    try:
        session, profile, next_text = await service.respond_to_question(
            db, session_id, payload.question_key, payload.answer
        )
        
        return SessionRespondResponse(
            session_id=session.id,
            status=session.status.value,
            profile_completion=profile.profile_completion,
            next_question_key=session.progress_state.current_key,
            next_question_text=next_text or "Discovery complete. Please proceed to generate the report.",
            profile_preview=profile.model_dump(exclude={"id", "session_id"})
        )
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except TviraException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{session_id}/complete", response_model=SessionDetailsResponse)
async def complete_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    service: SessionService = Depends(get_session_service)
):
    """Finalizes a session, maps context tags, and seals the business profile."""
    try:
        session, profile = await service.complete_session(db, session_id)
        
        # Reload derived facts
        c_query = select(BusinessContextORM).where(BusinessContextORM.session_id == session_id)
        c_result = await db.execute(c_query)
        context_orm = c_result.scalars().first()
        facts = context_orm.facts if context_orm else {}

        return SessionDetailsResponse(
            session=SessionResponse.model_validate(session),
            profile=BusinessProfileSchema.model_validate(profile),
            derived_facts=facts
        )
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except TviraException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{session_id}/lead", response_model=SessionResponse)
async def submit_lead_capture(
    session_id: UUID,
    payload: LeadCaptureRequest,
    db: AsyncSession = Depends(get_db_session),
    service: SessionService = Depends(get_session_service)
):
    """Captures lead details and updates status sequence to LEAD_CAPTURED."""
    try:
        session = await service.capture_lead(db, session_id, payload.name, payload.email, payload.phone)
        return SessionResponse.model_validate(session)
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except TviraException as e:
        raise HTTPException(status_code=400, detail=str(e))
