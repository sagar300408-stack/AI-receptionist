from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field
from app.domain.entities.profile import BusinessProfile
from app.domain.entities.constraint import Constraint
from app.domain.applicability import AIApplicability, ApplicabilityCategory

class SolutionType(str, Enum):
    AI_RECEPTIONIST = "AI_RECEPTIONIST"
    CRM_AUTOMATION = "CRM_AUTOMATION"
    APPOINTMENT_SCHEDULING = "APPOINTMENT_SCHEDULING"
    WORKFLOW_AUTOMATION = "WORKFLOW_AUTOMATION"
    LEAD_SCORING = "LEAD_SCORING"
    DOCUMENT_PROCESSING = "DOCUMENT_PROCESSING"
    CUSTOMER_SUPPORT_AUTOMATION = "CUSTOMER_SUPPORT_AUTOMATION"
    UNKNOWN = "UNKNOWN"

class SolutionEvidence(BaseModel):
    source: str
    value: Any
    reason: str

class RecommendedSolution(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    constraint_id: UUID
    solution_type: SolutionType
    confidence: int
    priority_score: int
    reasoning: str
    evidence: List[SolutionEvidence] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)

class SolutionCatalog(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    solution_type: SolutionType
    description: str
    supported_constraints: List[str] = Field(default_factory=list)  # Constraint categories
    supported_industries: List[str] = Field(default_factory=list)    # E.g. ["Education", "Real Estate"] or ["*"]
    minimum_applicability: int = 40
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)

class SolutionRecommendationPolicy:
    """Evaluates AI applicability results against the solution catalog to recommend solution architectures."""

    @staticmethod
    def evaluate(
        profile: BusinessProfile,
        constraint: Constraint,
        applicability: AIApplicability,
        catalog_entry: SolutionCatalog
    ) -> Optional[RecommendedSolution]:
        """Evaluates if a solution is recommended based on applicability results, constraint, and catalog rules."""
        # 1. Check applicability category eligibility: HIGHLY_APPLICABLE or MODERATELY_APPLICABLE
        eligible_categories = {
            ApplicabilityCategory.HIGHLY_APPLICABLE,
            ApplicabilityCategory.MODERATELY_APPLICABLE
        }
        # Handle string comparison in case enum/str type mismatch occurs
        app_category_str = applicability.category.value if isinstance(applicability.category, Enum) else str(applicability.category)
        if app_category_str not in [c.value for c in eligible_categories]:
            return None

        # 2. Check applicability score >= catalog minimum requirement
        if applicability.applicability_score < catalog_entry.minimum_applicability:
            return None

        # 3. Check if constraint category is supported
        constraint_cat_str = constraint.category.value if isinstance(constraint.category, Enum) else str(constraint.category)
        supported_constraints_upper = [c.upper() for c in catalog_entry.supported_constraints]
        if constraint_cat_str.upper() not in supported_constraints_upper and "*" not in catalog_entry.supported_constraints:
            return None

        # 4. Check if industry is supported (wildcard "*" matches everything, or if list is empty it defaults to true)
        industry_supported = False
        if not catalog_entry.supported_industries or "*" in catalog_entry.supported_industries:
            industry_supported = True
        else:
            profile_industry = (profile.industry or "").strip().upper()
            supported_industries_upper = [ind.strip().upper() for ind in catalog_entry.supported_industries]
            if profile_industry in supported_industries_upper:
                industry_supported = True
        
        if not industry_supported:
            return None

        # 5. Calculate priority score:
        # priority_score = round(applicability_score * 0.4 + impact_score * 0.4 + confidence * 0.2)
        # where impact_score and confidence are from Constraint, applicability_score from AIApplicability.
        impact_score = constraint.impact_score or 0
        constraint_confidence = constraint.confidence or 0
        app_score = applicability.applicability_score or 0
        priority_score = round(app_score * 0.4 + impact_score * 0.4 + constraint_confidence * 0.2)

        # 6. Generate structured evidence
        evidence_items = [
            SolutionEvidence(
                source="applicability_score",
                value=app_score,
                reason=f"Applicability score {app_score} satisfies minimum requirement of {catalog_entry.minimum_applicability}."
            ),
            SolutionEvidence(
                source="constraint_impact",
                value=impact_score,
                reason=f"Constraint impact score is {impact_score}."
            ),
            SolutionEvidence(
                source="constraint_confidence",
                value=constraint_confidence,
                reason=f"Constraint classification confidence is {constraint_confidence}%."
            )
        ]

        # Formatting reasoning summary
        reasoning = (
            f"Recommended '{catalog_entry.name}' because constraint '{constraint_cat_str}' "
            f"has high applicability ({app_score}) and impact ({impact_score})."
        )

        return RecommendedSolution(
            session_id=profile.session_id,
            constraint_id=constraint.id,
            solution_type=catalog_entry.solution_type,
            confidence=applicability.confidence,
            priority_score=priority_score,
            reasoning=reasoning,
            evidence=evidence_items
        )
