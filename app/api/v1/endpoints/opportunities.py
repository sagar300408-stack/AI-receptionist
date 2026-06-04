from uuid import UUID
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db_session
from app.core.exceptions import TviraException, SessionNotFoundError
from app.models.opportunity import (
    OpportunityEvaluationORM, OpportunityResultORM, OpportunityEvidenceORM,
    OpportunityTemplateORM, OpportunityGroupORM, ScoringProfileORM
)
from app.schemas.opportunity import (
    SessionOpportunitiesResponse, OpportunityResultSchema, OpportunityEvidenceSchema
)
from app.services.opportunity import OpportunityEngine

router = APIRouter()

@router.post("/{session_id}/evaluate", response_model=SessionOpportunitiesResponse)
async def evaluate_opportunities(
    session_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Manually executes the Segment 2 Opportunity engine on the session profile."""
    try:
        engine = OpportunityEngine()
        evaluation_orm = await engine.evaluate_session_opportunities(db, session_id)
        return await _build_opportunities_response(db, evaluation_orm)
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except TviraException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{session_id}/opportunities", response_model=SessionOpportunitiesResponse)
async def get_session_opportunities(
    session_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Retrieves computed business opportunities and matching audit evidence for a session."""
    # Find latest evaluation for this session
    eval_query = select(OpportunityEvaluationORM).where(
        OpportunityEvaluationORM.session_id == session_id
    ).order_by(OpportunityEvaluationORM.evaluated_at.desc())
    
    eval_result = await db.execute(eval_query)
    evaluation = eval_result.scalars().first()
    
    if not evaluation:
        raise HTTPException(
            status_code=404, 
            detail=f"No opportunity evaluations found for session {session_id}. Please finalize the discovery session first."
        )
        
    return await _build_opportunities_response(db, evaluation)

async def _build_opportunities_response(
    db: AsyncSession, evaluation: OpportunityEvaluationORM
) -> SessionOpportunitiesResponse:
    """Helper compiler to fetch and serialize database models into the response schema contract."""
    # Fetch scoring profile name
    sp_name = "Standard Scoring Profile"
    if evaluation.scoring_profile_id:
        sp = await db.get(ScoringProfileORM, evaluation.scoring_profile_id)
        if sp:
            sp_name = sp.name

    # Fetch results for this evaluation
    res_query = select(OpportunityResultORM).where(
        OpportunityResultORM.evaluation_id == evaluation.id
    )
    res_result = await db.execute(res_query)
    results = list(res_result.scalars().all())

    # Build response mappings grouped by group name
    groups_dict: Dict[str, List[OpportunityResultSchema]] = {}

    for r in results:
        # Load template and group details
        template = await db.get(OpportunityTemplateORM, r.template_id)
        group_name = "Uncategorized Automation"
        
        if template and template.group_id:
            group = await db.get(OpportunityGroupORM, template.group_id)
            if group:
                group_name = group.name

        # Load evidence records
        ev_query = select(OpportunityEvidenceORM).where(
            OpportunityEvidenceORM.result_id == r.id
        )
        ev_result = await db.execute(ev_query)
        evidence_list = list(ev_result.scalars().all())
        
        schemas_evidence = [
            OpportunityEvidenceSchema(
                field=ev.field,
                value=ev.value,
                operator=ev.operator,
                rule_expression=ev.rule_expression
            ) for ev in evidence_list
        ]

        result_schema = OpportunityResultSchema(
            opportunity_code=template.code if template else "UNKNOWN",
            name=template.name if template else "Unknown Opportunity",
            priority=r.priority,
            confidence=r.confidence,
            impact_score=r.impact_score,
            complexity_score=r.complexity_score,
            reasoning=r.reasoning or [],
            evidence=schemas_evidence
        )

        if group_name not in groups_dict:
            groups_dict[group_name] = []
        groups_dict[group_name].append(result_schema)

    return SessionOpportunitiesResponse(
        evaluation_id=evaluation.id,
        engine_version=evaluation.engine_version,
        ruleset_version=evaluation.ruleset_version,
        scoring_profile=sp_name,
        groups=groups_dict
    )
