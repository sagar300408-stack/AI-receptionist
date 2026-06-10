import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db_session
from app.models.session import SessionORM
from app.models.review import ReviewSessionORM, FounderReviewORM, FounderFeedbackORM
from app.schemas.review import (
    ReviewSessionResponseSchema,
    ReviewSessionSchema,
    FounderReviewSchema,
    FounderFeedbackSchema,
    StartSessionRequest,
    ApproveRequest,
    RejectRequest,
    ResearchRequest,
    ArchiveRequest,
    FeedbackRequest,
)
from app.services.founder_review_engine import FounderReviewEngine

logger = logging.getLogger("tvira.api.reviews")

router = APIRouter()

@router.get("/sessions/{session_id}", response_model=ReviewSessionResponseSchema)
async def get_review_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Retrieves the review session container and all associated solution reviews for a session."""
    session_orm = await db.get(SessionORM, session_id)
    if not session_orm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session {session_id} not found.")

    sess_query = select(ReviewSessionORM).where(ReviewSessionORM.session_id == session_id)
    sess_result = await db.execute(sess_query)
    review_session = sess_result.scalars().first()

    if not review_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No review session found for session {session_id}. Please run recommendation engine first."
        )

    rev_query = select(FounderReviewORM).where(FounderReviewORM.review_session_id == review_session.id)
    rev_result = await db.execute(rev_query)
    reviews_list = list(rev_result.scalars().all())

    return ReviewSessionResponseSchema(
        session=ReviewSessionSchema.from_orm(review_session),
        reviews=[FounderReviewSchema.from_orm(r) for r in reviews_list]
    )

@router.post("/sessions/{session_id}/start", response_model=ReviewSessionSchema)
async def start_review_session(
    session_id: UUID,
    req: StartSessionRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Starts the human validation phase for a review session under a specified reviewer."""
    try:
        engine = FounderReviewEngine()
        sess = await engine.start_review_session(db, session_id, req.reviewer)
        return ReviewSessionSchema.from_orm(sess)
    except Exception as e:
        logger.error(f"Error starting review session for session {session_id}: {e}")
        err_msg = str(e)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

@router.post("/sessions/{session_id}/complete", response_model=ReviewSessionSchema)
async def complete_review_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Completes the review session container, finalizing the audit and triggering opportunity intelligence."""
    try:
        engine = FounderReviewEngine()
        sess = await engine.complete_review_session(db, session_id)
        return ReviewSessionSchema.from_orm(sess)
    except Exception as e:
        logger.error(f"Error completing review session for session {session_id}: {e}")
        err_msg = str(e)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

@router.post("/{id}/approve", response_model=FounderReviewSchema)
async def approve_recommendation(
    id: UUID,
    req: ApproveRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Approves a recommended solution, setting validation reasons, scores, and enabling opportunity intelligence."""
    try:
        engine = FounderReviewEngine()
        rev = await engine.approve_recommendation(
            db,
            review_id=id,
            reviewer=req.reviewer,
            priority_score=req.priority_score,
            priority_level=req.priority_level,
            commercial_readiness=req.commercial_readiness,
            decision_reason=req.decision_reason,
            comment=req.comment,
            evidence_notes=req.evidence_notes
        )
        return FounderReviewSchema.from_orm(rev)
    except Exception as e:
        logger.error(f"Error approving review {id}: {e}")
        err_msg = str(e)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

@router.post("/{id}/reject", response_model=FounderReviewSchema)
async def reject_recommendation(
    id: UUID,
    req: RejectRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Rejects a recommended solution with standard validation reason tags."""
    try:
        engine = FounderReviewEngine()
        rev = await engine.reject_recommendation(
            db,
            review_id=id,
            decision_reason=req.decision_reason,
            comment=req.comment,
            evidence_notes=req.evidence_notes
        )
        return FounderReviewSchema.from_orm(rev)
    except Exception as e:
        logger.error(f"Error rejecting review {id}: {e}")
        err_msg = str(e)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

@router.post("/{id}/research", response_model=FounderReviewSchema)
async def research_recommendation(
    id: UUID,
    req: ResearchRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Flags a recommended solution as needing research before any approval can happen."""
    try:
        engine = FounderReviewEngine()
        rev = await engine.research_recommendation(db, id, req.comment)
        return FounderReviewSchema.from_orm(rev)
    except Exception as e:
        logger.error(f"Error flagging review {id} for research: {e}")
        err_msg = str(e)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

@router.post("/{id}/archive", response_model=FounderReviewSchema)
async def archive_recommendation(
    id: UUID,
    req: ArchiveRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Archives a recommended solution to hide or disable it from immediate review queues."""
    try:
        engine = FounderReviewEngine()
        rev = await engine.archive_recommendation(db, id, req.comment)
        return FounderReviewSchema.from_orm(rev)
    except Exception as e:
        logger.error(f"Error archiving review {id}: {e}")
        err_msg = str(e)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

@router.post("/{id}/feedback", response_model=FounderFeedbackSchema)
async def add_review_feedback(
    id: UUID,
    req: FeedbackRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Registers institutional feedback notes directly on an active review item."""
    try:
        now = datetime.now(timezone.utc)
        review = await db.get(FounderReviewORM, id)
        if not review:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"FounderReview {id} not found.")

        feedback = FounderFeedbackORM(
            id=uuid4(),
            review_id=id,
            comment=req.comment,
            decision_reason=req.decision_reason or review.decision_reason,
            evidence_notes=req.evidence_notes,
            created_at=now
        )
        db.add(feedback)
        await db.commit()
        await db.refresh(feedback)
        return FounderFeedbackSchema.from_orm(feedback)
    except Exception as e:
        logger.error(f"Error adding feedback to review {id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
