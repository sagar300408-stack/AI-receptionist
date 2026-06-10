import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db_session
from app.models.session import SessionORM
from app.models.solution import RecommendedSolutionORM
from app.schemas.solution import (
    SolutionResponse,
    RecommendedSolutionSchema,
    SolutionEvidenceSchema,
)
from app.services.solution_recommendation_engine import SolutionRecommendationEngine

logger = logging.getLogger("tvira.api.solutions")

router = APIRouter()

@router.get("/{session_id}/solutions", response_model=SolutionResponse)
async def get_session_solutions(
    session_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Retrieves solution recommendation results and evidence traces for a session."""
    # Check if session exists first
    session_orm = await db.get(SessionORM, session_id)
    if not session_orm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session {session_id} not found.")

    query = select(RecommendedSolutionORM).where(RecommendedSolutionORM.session_id == session_id)
    result = await db.execute(query)
    sol_results = list(result.scalars().all())

    if not sol_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No recommended solutions found for session {session_id}. Please complete discovery first."
        )

    results_list = []
    for s in sol_results:
        evidence_list = []
        if isinstance(s.evidence, list):
            for e in s.evidence:
                if isinstance(e, dict):
                    evidence_list.append(
                        SolutionEvidenceSchema(
                            source=e.get("source", "unknown"),
                            value=e.get("value"),
                            reason=e.get("reason", "")
                        )
                    )
        results_list.append(
            RecommendedSolutionSchema(
                id=s.id,
                session_id=s.session_id,
                constraint_id=s.constraint_id,
                solution_type=s.solution_type,
                confidence=s.confidence,
                priority_score=s.priority_score,
                reasoning=s.reasoning,
                evidence=evidence_list,
                created_at=s.created_at
            )
        )

    return SolutionResponse(session_id=session_id, results=results_list)

@router.post("/{session_id}/solutions/recalculate", response_model=SolutionResponse)
async def recalculate_solutions(
    session_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Manually recalculates/re-evaluates solution recommendations for a session."""
    try:
        engine = SolutionRecommendationEngine()
        sol_results = await engine.evaluate_session_solutions(db, session_id)

        results_list = []
        for s in sol_results:
            evidence_list = []
            if isinstance(s.evidence, list):
                for e in s.evidence:
                    if isinstance(e, dict):
                        evidence_list.append(
                            SolutionEvidenceSchema(
                                source=e.get("source", "unknown"),
                                value=e.get("value"),
                                reason=e.get("reason", "")
                            )
                        )
            results_list.append(
                RecommendedSolutionSchema(
                    id=s.id,
                    session_id=s.session_id,
                    constraint_id=s.constraint_id,
                    solution_type=s.solution_type,
                    confidence=s.confidence,
                    priority_score=s.priority_score,
                    reasoning=s.reasoning,
                    evidence=evidence_list,
                    created_at=s.created_at
                )
            )

        return SolutionResponse(session_id=session_id, results=results_list)
    except Exception as e:
        logger.error(f"Error recalculating solutions for session {session_id}: {e}")
        err_msg = str(e)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
