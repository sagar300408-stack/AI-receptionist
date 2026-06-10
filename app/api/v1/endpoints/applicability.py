import logging
from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db_session
from app.models.session import SessionORM
from app.models.applicability import AIApplicabilityORM, ReviewQueueORM
from app.schemas.applicability import (
    ApplicabilityResponse,
    ApplicabilitySchema,
    ApplicabilityEvidenceSchema,
    ReviewQueueSchema,
)
from app.services.applicability_engine import AIApplicabilityEngine

logger = logging.getLogger("tvira.api.applicability")

router = APIRouter()

@router.get("/{session_id}/applicability", response_model=ApplicabilityResponse)
async def get_session_applicability(
    session_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Retrieves AI applicability results and evidence trace logs for a session."""
    # Check if session exists first
    session_orm = await db.get(SessionORM, session_id)
    if not session_orm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session {session_id} not found.")

    query = select(AIApplicabilityORM).where(AIApplicabilityORM.session_id == session_id)
    result = await db.execute(query)
    app_results = list(result.scalars().all())

    if not app_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No applicability evaluations found for session {session_id}. Please complete discovery first."
        )

    results_list = []
    for a in app_results:
        evidence_list = []
        if isinstance(a.evidence, list):
            for e in a.evidence:
                if isinstance(e, dict):
                    evidence_list.append(
                        ApplicabilityEvidenceSchema(
                            source=e.get("source", "unknown"),
                            value=e.get("value"),
                            reason=e.get("reason", "")
                        )
                    )
        results_list.append(
            ApplicabilitySchema(
                id=a.id,
                session_id=a.session_id,
                constraint_id=a.constraint_id,
                applicability_score=a.applicability_score,
                confidence=a.confidence,
                category=a.category,
                reasoning=a.reasoning,
                evidence=evidence_list,
                recommended_solution_types=a.recommended_solution_types or [],
                rule_version=a.rule_version,
                created_at=a.created_at
            )
        )

    return ApplicabilityResponse(session_id=session_id, results=results_list)

@router.post("/{session_id}/applicability/recalculate", response_model=ApplicabilityResponse)
async def recalculate_applicability(
    session_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Manually recalculates/re-evaluates AI applicability for a session constraint profile."""
    try:
        engine = AIApplicabilityEngine()
        app_results = await engine.evaluate_session_applicability(db, session_id)

        results_list = []
        for a in app_results:
            evidence_list = []
            if isinstance(a.evidence, list):
                for e in a.evidence:
                    if isinstance(e, dict):
                        evidence_list.append(
                            ApplicabilityEvidenceSchema(
                                source=e.get("source", "unknown"),
                                value=e.get("value"),
                                reason=e.get("reason", "")
                            )
                        )
            results_list.append(
                ApplicabilitySchema(
                    id=a.id,
                    session_id=a.session_id,
                    constraint_id=a.constraint_id,
                    applicability_score=a.applicability_score,
                    confidence=a.confidence,
                    category=a.category,
                    reasoning=a.reasoning,
                    evidence=evidence_list,
                    recommended_solution_types=a.recommended_solution_types or [],
                    rule_version=a.rule_version,
                    created_at=a.created_at
                )
            )

        return ApplicabilityResponse(session_id=session_id, results=results_list)
    except Exception as e:
        logger.error(f"Error recalculating applicability for session {session_id}: {e}")
        err_msg = str(e)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

@router.get("/{session_id}/review-queue", response_model=List[ReviewQueueSchema])
async def get_session_review_queue(
    session_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Retrieves manual review queue entries captured for a session."""
    # Check if session exists first
    session_orm = await db.get(SessionORM, session_id)
    if not session_orm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session {session_id} not found.")

    query = select(ReviewQueueORM).where(ReviewQueueORM.session_id == session_id)
    result = await db.execute(query)
    queue_items = list(result.scalars().all())

    return [
        ReviewQueueSchema(
            id=q.id,
            session_id=q.session_id,
            constraint_id=q.constraint_id,
            reason=q.reason,
            priority=q.priority,
            created_at=q.created_at
        ) for q in queue_items
    ]
