from typing import List, Dict, Any, Optional
from app.domain.entities.profile import BusinessProfile
from app.domain.entities.constraint import Constraint, ConstraintRule
from app.domain.value_objects.constraint import ConstraintCategory, ConstraintEvidence
from app.domain.policies.eligibility import ConditionEvaluator

class ConstraintClassificationPolicy:
    """Evaluates business profile signals against rules and classifies constraints."""

    @staticmethod
    def classify(
        profile: BusinessProfile,
        active_rules: List[ConstraintRule],
        context_facts: Optional[Dict[str, Any]] = None
    ) -> List[Constraint]:
        """Evaluates active database-driven rules and produces Constraint entities."""
        context_facts = context_facts or {}
        evaluator = ConditionEvaluator(profile, context_facts)
        detected_constraints: List[Constraint] = []

        for rule in active_rules:
            if not rule.active:
                continue

            if evaluator.evaluate(rule.conditions):
                # 1. Trace fields used in the rule to extract origin keys
                origin_fields = ConstraintClassificationPolicy._extract_fields(rule.conditions)
                
                # Filter origin fields to only those present in profile/facts
                valid_origin = []
                evidence_items: List[ConstraintEvidence] = []
                
                for f in origin_fields:
                    val = None
                    resolved = False
                    if hasattr(profile, f):
                        val = getattr(profile, f)
                        resolved = True
                    elif f in context_facts:
                        val = context_facts[f]
                        resolved = True
                        
                    if resolved and val is not None:
                        valid_origin.append(f)
                        
                        # Generate structured evidence for this signal
                        reason = f"Signal field '{f}' evaluated to '{val}' matching rule conditions."
                        if f == "monthly_leads":
                            reason = f"Monthly leads volume of {val} exceeds rule thresholds."
                        elif f == "team_size":
                            reason = f"Team size of {val} members indicates scale complexity."
                        elif f == "pain_points":
                            reason = f"Pain point matching rule: {val}."
                        
                        evidence_items.append(
                            ConstraintEvidence(
                                source=f,
                                value=val,
                                reason=reason
                            )
                        )

                # 2. Format the narrative evidence template and append
                format_dict = {
                    "monthly_leads": profile.monthly_leads or 0,
                    "monthly_customers": profile.monthly_customers or 0,
                    "team_size": profile.team_size or 0,
                    "business_type": profile.business_type or "Generic",
                    "pain_point": ", ".join(profile.pain_points) if profile.pain_points else "delayed responses"
                }
                
                try:
                    narrative_reason = rule.evidence_template.format(**format_dict)
                except Exception:
                    narrative_reason = rule.evidence_template

                evidence_items.append(
                    ConstraintEvidence(
                        source="rule_narrative",
                        value=rule.name,
                        reason=narrative_reason
                    )
                )

                detected_constraints.append(
                    Constraint(
                        session_id=profile.session_id,
                        category=rule.category,
                        confidence=rule.base_confidence,
                        severity=rule.severity,
                        impact_score=rule.base_impact,
                        evidence=evidence_items,
                        origin=valid_origin
                    )
                )

        # 3. Apply Unknown Constraint Policy
        unknown_constraint = UnknownConstraintPolicy.evaluate_unknown(profile, detected_constraints, context_facts)
        if unknown_constraint:
            detected_constraints.append(unknown_constraint)

        return detected_constraints

    @staticmethod
    def _extract_fields(conditions: Any) -> List[str]:
        """Helper to recursively extract all field keys referenced in rule conditions."""
        fields = []
        if not conditions:
            return fields
        if isinstance(conditions, list):
            for c in conditions:
                fields.extend(ConstraintClassificationPolicy._extract_fields(c))
        elif isinstance(conditions, dict):
            if "and" in conditions:
                for c in conditions["and"]:
                    fields.extend(ConstraintClassificationPolicy._extract_fields(c))
            elif "or" in conditions:
                for c in conditions["or"]:
                    fields.extend(ConstraintClassificationPolicy._extract_fields(c))
            elif "not" in conditions:
                fields.extend(ConstraintClassificationPolicy._extract_fields(conditions["not"]))
            elif "field" in conditions:
                fields.append(conditions["field"])
        return list(set(fields))


class UnknownConstraintPolicy:
    """Evaluates conflicting signals or lack of constraints to trigger manual reviews."""

    @staticmethod
    def evaluate_unknown(
        profile: BusinessProfile,
        detected_constraints: List[Constraint],
        context_facts: Dict[str, Any]
    ) -> Optional[Constraint]:
        """Returns an UNKNOWN constraint if fallback criteria are met."""
        trigger_unknown = False
        reasons = []

        # A. Lack of matches
        if not detected_constraints:
            trigger_unknown = True
            reasons.append("No active bottleneck rules matched the business profile signals.")

        # B. All matches have very low confidence
        elif all(c.confidence < 40 for c in detected_constraints):
            max_conf = max(c.confidence for c in detected_constraints)
            trigger_unknown = True
            reasons.append(f"All matched constraints yielded low confidence (highest: {max_conf}%).")

        # C. Conflicting signals
        leads = profile.monthly_leads or 0
        customers = profile.monthly_customers or 0
        if leads >= 500 and customers <= 0:
            trigger_unknown = True
            reasons.append(f"Conflicting conversion metric: high leads volume ({leads}/mo) but zero paying customers ({customers}/mo).")

        if trigger_unknown:
            evidence = []
            origin = []
            for r in reasons:
                evidence.append(
                    ConstraintEvidence(
                        source="unknown_policy_audit",
                        value={"leads": leads, "customers": customers},
                        reason=r
                    )
                )
                origin.append("unknown_policy_audit")

            return Constraint(
                session_id=profile.session_id,
                category=ConstraintCategory.UNKNOWN,
                confidence=30,
                severity="HIGH",
                impact_score=50,
                evidence=evidence,
                origin=origin
            )

        return None
