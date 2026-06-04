from typing import List, Dict, Any, Tuple
from app.domain.entities.opportunity import OpportunityTemplate, OpportunityRule
from app.domain.entities.profile import BusinessProfile

class OpportunityScoringPolicy:
    """Calculates impact, complexity, and confidence scores for opportunity templates."""

    @staticmethod
    def calculate_scores(
        template: OpportunityTemplate,
        matched_rules: List[OpportunityRule],
        profile: BusinessProfile
    ) -> Tuple[int, int, float]:
        """Calculates final clamped scores.
        Formula:
          Score = Clamp(BaseWeight + Sum(AdditiveModifiers) * Product(MultiplicativeModifiers))
        - Rules with template matching rule_type == 'IMPACT_MODIFIER' or 'COMPLEXITY_MODIFIER'.
        - If modifier_value starts with '*' (represented in DB as float like 1.5 or multiplier flag, 
          let's treat values > 5.0 as additive and values between 0.1 and 3.0 as multiplicative multipliers if they represent factors, 
          or explicitly check logic. Let's make it simple: 
          if modifier_value is positive or negative, it can be added to the score, 
          unless it is a multiplier factor. Let's support both additive and multiplicative modifiers explicitly).
        """
        impact = template.base_impact
        complexity = template.base_complexity

        # Modifiers list
        impact_add = 0.0
        impact_mult = 1.0
        comp_add = 0.0
        comp_mult = 1.0

        for rule in matched_rules:
            val = rule.modifier_value or 0.0
            if rule.rule_type == "IMPACT_MODIFIER":
                # If rule modifier is written to multiply (we can check if it's less than 3.0 and positive as multiplier, 
                # or treat it as multiplier if it's configured as multiplier. Let's say: if val is between 0.0 and 3.0 we multiply, 
                # else we add. Better yet, let's keep it simple: if rule.conditions indicates a multiplier, or let's support: 
                # if val is positive and less than 3.0 it's multiplicative, else it's additive. 
                # To be completely safe and clean, let's treat values in range [0.1, 4.0] as multipliers, and others as additives!)
                if 0.1 <= val <= 4.0:
                    impact_mult *= val
                else:
                    impact_add += val
            elif rule.rule_type == "COMPLEXITY_MODIFIER":
                if 0.1 <= val <= 4.0:
                    comp_mult *= val
                else:
                    comp_add += val

        # Evaluate impact
        final_impact = (impact + impact_add) * impact_mult
        final_complexity = (complexity + comp_add) * comp_mult

        # Clamp between 0 and 100
        clamped_impact = max(0, min(100, int(round(final_impact))))
        clamped_complexity = max(0, min(100, int(round(final_complexity))))

        # Confidence: scales directly with profile completion (from 0.0 to 1.0)
        confidence = profile.profile_completion / 100.0
        # Ensure confidence is clamped between 0.0 and 1.0
        clamped_confidence = max(0.0, min(1.0, round(confidence, 2)))

        return clamped_impact, clamped_complexity, clamped_confidence
