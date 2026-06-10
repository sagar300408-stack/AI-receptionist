from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field
from app.domain.entities.profile import BusinessProfile
from app.domain.entities.constraint import Constraint
from app.domain.policies.eligibility import ConditionEvaluator

class ApplicabilityCategory(str, Enum):
    HIGHLY_APPLICABLE = "HIGHLY_APPLICABLE"
    MODERATELY_APPLICABLE = "MODERATELY_APPLICABLE"
    LOW_APPLICABILITY = "LOW_APPLICABILITY"
    NOT_RECOMMENDED = "NOT_RECOMMENDED"
    MANUAL_REVIEW = "MANUAL_REVIEW"

class SolutionType(str, Enum):
    AI_RECEPTIONIST = "AI_RECEPTIONIST"
    CRM_AUTOMATION = "CRM_AUTOMATION"
    APPOINTMENT_SCHEDULING = "APPOINTMENT_SCHEDULING"
    LEAD_QUALIFICATION = "LEAD_QUALIFICATION"
    WORKFLOW_AUTOMATION = "WORKFLOW_AUTOMATION"
    DOCUMENT_PROCESSING = "DOCUMENT_PROCESSING"
    CUSTOMER_SUPPORT_AUTOMATION = "CUSTOMER_SUPPORT_AUTOMATION"
    UNKNOWN = "UNKNOWN"

class ApplicabilityEvidence(BaseModel):
    source: str
    value: Any
    reason: str

class AIApplicability(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    constraint_id: UUID
    applicability_score: int
    confidence: int
    category: ApplicabilityCategory
    reasoning: str
    evidence: List[ApplicabilityEvidence] = Field(default_factory=list)
    recommended_solution_types: List[SolutionType] = Field(default_factory=list)
    rule_version: str
    created_at: datetime = Field(default_factory=datetime.now)

class ApplicabilityRule(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    version: str = "1.0"
    constraint_category: str
    conditions: Dict[str, Any]
    applicability_score: int
    confidence: int
    category: ApplicabilityCategory
    reasoning_template: str
    recommended_solution_types: List[SolutionType] = Field(default_factory=list)
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)

class ApplicabilityEvaluationPolicy:
    """Evaluates constraint applicability against rules using the business profile."""

    @staticmethod
    def evaluate(
        profile: BusinessProfile,
        constraint: Constraint,
        active_rules: List[ApplicabilityRule],
        context_facts: Dict[str, Any]
    ) -> AIApplicability:
        
        # Filter rules for this constraint category
        matching_rules = [
            r for r in active_rules 
            if r.constraint_category == constraint.category.value and r.active
        ]

        # Setup evaluation context facts
        eval_facts = dict(context_facts)
        # Ensure constraint fields are directly accessible
        eval_facts["constraint_category"] = constraint.category.value
        eval_facts["severity"] = constraint.severity
        eval_facts["impact_score"] = constraint.impact_score
        eval_facts["confidence"] = constraint.confidence

        evaluator = ConditionEvaluator(profile, eval_facts)
        matched_rule: Optional[ApplicabilityRule] = None

        for rule in matching_rules:
            if evaluator.evaluate(rule.conditions):
                matched_rule = rule
                break

        # Fallback if no matching rule
        if not matched_rule:
            evidence = [
                ApplicabilityEvidence(
                    source="policy_fallback",
                    value=constraint.category.value,
                    reason=f"No matching applicability rule evaluated to True for constraint: {constraint.category.value}."
                )
            ]
            return AIApplicability(
                session_id=profile.session_id,
                constraint_id=constraint.id,
                applicability_score=0,
                confidence=0,
                category=ApplicabilityCategory.MANUAL_REVIEW,
                reasoning=f"No applicability rule matched the business signals for constraint category: {constraint.category.value}.",
                evidence=evidence,
                recommended_solution_types=[SolutionType.UNKNOWN],
                rule_version="N/A"
            )

        # Build evidence
        fields = ApplicabilityEvaluationPolicy._extract_fields(matched_rule.conditions)
        evidence_items: List[ApplicabilityEvidence] = []

        for f in fields:
            val = None
            resolved = False
            if hasattr(profile, f):
                val = getattr(profile, f)
                resolved = True
            elif f in eval_facts:
                val = eval_facts[f]
                resolved = True

            if resolved and val is not None:
                evidence_items.append(
                    ApplicabilityEvidence(
                        source=f,
                        value=val,
                        reason=f"Field '{f}' evaluated to '{val}' matching applicability conditions."
                    )
                )

        # Format reasoning summary
        format_dict = {
            "monthly_leads": profile.monthly_leads or 0,
            "monthly_customers": profile.monthly_customers or 0,
            "team_size": profile.team_size or 0,
            "business_type": profile.business_type or "Generic",
            "severity": constraint.severity,
            "impact_score": constraint.impact_score,
            "confidence": constraint.confidence,
        }
        try:
            reasoning = matched_rule.reasoning_template.format(**format_dict)
        except Exception:
            reasoning = matched_rule.reasoning_template

        evidence_items.append(
            ApplicabilityEvidence(
                source="rule_narrative",
                value=matched_rule.name,
                reason=reasoning
            )
        )

        # Resolve category based on score thresholds
        score = matched_rule.applicability_score
        category = ApplicabilityCategory.MANUAL_REVIEW
        if 90 <= score <= 100:
            category = ApplicabilityCategory.HIGHLY_APPLICABLE
        elif 70 <= score <= 89:
            category = ApplicabilityCategory.MODERATELY_APPLICABLE
        elif 40 <= score <= 69:
            category = ApplicabilityCategory.LOW_APPLICABILITY
        elif 0 <= score <= 39:
            category = ApplicabilityCategory.NOT_RECOMMENDED

        return AIApplicability(
            session_id=profile.session_id,
            constraint_id=constraint.id,
            applicability_score=score,
            confidence=matched_rule.confidence,
            category=category,
            reasoning=reasoning,
            evidence=evidence_items,
            recommended_solution_types=matched_rule.recommended_solution_types or [SolutionType.UNKNOWN],
            rule_version=matched_rule.version
        )

    @staticmethod
    def _extract_fields(conditions: Any) -> List[str]:
        """Recursively extract field keys from conditions dictionary."""
        fields = []
        if not conditions:
            return fields
        if isinstance(conditions, list):
            for c in conditions:
                fields.extend(ApplicabilityEvaluationPolicy._extract_fields(c))
        elif isinstance(conditions, dict):
            if "and" in conditions:
                for c in conditions["and"]:
                    fields.extend(ApplicabilityEvaluationPolicy._extract_fields(c))
            elif "or" in conditions:
                for c in conditions["or"]:
                    fields.extend(ApplicabilityEvaluationPolicy._extract_fields(c))
            elif "not" in conditions:
                fields.extend(ApplicabilityEvaluationPolicy._extract_fields(conditions["not"]))
            elif "field" in conditions:
                fields.append(conditions["field"])
        return list(set(fields))
