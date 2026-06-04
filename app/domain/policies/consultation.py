from typing import List, Dict, Any
from app.domain.entities.consultation import ConsultationRecommendation
from app.domain.entities.qualification import QualificationResult
from app.domain.value_objects.report import LeadGrade

class ConsultationPolicy:
    """Policy mapping the criteria under which booking consultations is recommended."""

    @staticmethod
    def evaluate_booking(
        qualification: QualificationResult,
        opportunities: List[Dict[str, Any]],
        consultation_version: str = "1.0"
    ) -> ConsultationRecommendation:
        """Determines if a booking scheduling invite is indicated.
        - Recommended = True if score >= 50 OR has 'CRITICAL' opportunities.
        - Confidence = 0.5 + (qualification_score / 200.0)
        """
        recommended = False
        reasons = []

        score = qualification.qualification_score
        has_critical = any(o.get("priority") == "CRITICAL" for o in opportunities)

        if score >= 50:
            recommended = True
            reasons.append(f"High-quality lead score ({score}/100) shows strong business potential.")

        if has_critical:
            recommended = True
            reasons.append("Critical automation opportunity discovered requiring custom scoping.")

        if qualification.lead_grade == LeadGrade.HOT:
            reasons.append("Priority business match classified under HOT grade.")

        if not recommended:
            reasons.append("Lead metrics suggest starting with self-serve learning materials first.")

        # Compute confidence score bounded to [0.5, 0.99]
        confidence = 0.5 + (score / 200.0)
        clamped_confidence = max(0.5, min(0.99, round(confidence, 2)))

        return ConsultationRecommendation(
            session_id=qualification.session_id,
            consultation_recommended=recommended,
            confidence=clamped_confidence,
            reasons=reasons,
            consultation_version=consultation_version
        )
