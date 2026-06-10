import logging
from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db_session
from app.models.constraint import ConstraintORM
from app.models.session import SessionORM
from app.schemas.constraint import (
    ConstraintDetailsResponse,
    ConstraintSchema,
    ConstraintEvidenceSchema,
)
from app.services.constraint_classifier import ConstraintClassifier

logger = logging.getLogger("tvira.api.constraints")

router = APIRouter()

@router.get("/{session_id}/constraints", response_model=ConstraintDetailsResponse)
async def get_session_constraints(
    session_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Retrieves classified business constraints and matched evidence for a session."""
    # Check if session exists first
    session_orm = await db.get(SessionORM, session_id)
    if not session_orm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session {session_id} not found.")

    query = select(ConstraintORM).where(ConstraintORM.session_id == session_id)
    result = await db.execute(query)
    constraints = list(result.scalars().all())

    if not constraints:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No constraints found for session {session_id}. Please finalize the discovery session first."
        )

    constraints_list = []
    for c in constraints:
        evidence_list = []
        if isinstance(c.evidence, list):
            for e in c.evidence:
                if isinstance(e, dict):
                    evidence_list.append(
                        ConstraintEvidenceSchema(
                            source=e.get("source", "unknown"),
                            value=e.get("value"),
                            reason=e.get("reason", "")
                        )
                    )
        
        constraints_list.append(
            ConstraintSchema(
                id=c.id,
                session_id=c.session_id,
                category=c.category,
                confidence=c.confidence,
                severity=c.severity,
                impact_score=c.impact_score,
                evidence=evidence_list,
                origin=c.origin or [],
                created_at=c.created_at
            )
        )

    return ConstraintDetailsResponse(session_id=session_id, constraints=constraints_list)

@router.post("/{session_id}/constraints/recalculate", response_model=ConstraintDetailsResponse)
async def recalculate_constraints(
    session_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Manually recalculates/reclassifies business constraints for a session."""
    try:
        classifier = ConstraintClassifier()
        constraints = await classifier.classify_session_constraints(db, session_id)

        constraints_list = []
        for c in constraints:
            evidence_list = []
            if isinstance(c.evidence, list):
                for e in c.evidence:
                    if isinstance(e, dict):
                        evidence_list.append(
                            ConstraintEvidenceSchema(
                                source=e.get("source", "unknown"),
                                value=e.get("value"),
                                reason=e.get("reason", "")
                            )
                        )

            constraints_list.append(
                ConstraintSchema(
                    id=c.id,
                    session_id=c.session_id,
                    category=c.category,
                    confidence=c.confidence,
                    severity=c.severity,
                    impact_score=c.impact_score,
                    evidence=evidence_list,
                    origin=c.origin or [],
                    created_at=c.created_at
                )
            )

        return ConstraintDetailsResponse(session_id=session_id, constraints=constraints_list)
    except Exception as e:
        logger.error(f"Error recalculating constraints for session {session_id}: {e}")
        err_msg = str(e)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
