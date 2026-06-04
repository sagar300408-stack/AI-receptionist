from typing import Dict, Any, List, Tuple
from app.domain.entities.profile import BusinessProfile
from app.domain.entities.qualification import QualificationResult
from app.domain.value_objects.report import LeadGrade, RoutingPath

class QualificationPolicy:
    """Calculates deterministic qualification scores, lead grades, and routing classifications."""

    @staticmethod
    def evaluate_qualification(
        profile: BusinessProfile,
        opportunities: List[Dict[str, Any]],
        qualification_version: str = "1.0"
    ) -> QualificationResult:
        """Determines business value score, grade, and routing pathway:
        1. Score components based on team size, lead volumes, and opportunity metrics.
        2. Assign Grade based on score thresholds (HOT/WARM/COLD).
        3. Match Routing path based on grade and scale metrics.
        """
        score = 0
        factors = []

        # A. Team Size check
        team = profile.team_size or 0
        if team > 20:
            score += 30
            factors.append({"factor": "team_size_gt_20", "points": 30, "detail": f"Team size {team} is large"})
        elif team > 5:
            score += 20
            factors.append({"factor": "team_size_gt_5", "points": 20, "detail": f"Team size {team} is medium"})
        else:
            factors.append({"factor": "team_size_low", "points": 0, "detail": f"Team size {team} is small"})

        # B. Leads check
        leads = profile.monthly_leads or 0
        if leads >= 500:
            score += 30
            factors.append({"factor": "monthly_leads_gt_500", "points": 30, "detail": f"Monthly leads {leads} is high"})
        elif leads >= 100:
            score += 20
            factors.append({"factor": "monthly_leads_gt_100", "points": 20, "detail": f"Monthly leads {leads} is medium"})
        else:
            factors.append({"factor": "monthly_leads_low", "points": 0, "detail": f"Monthly leads {leads} is low"})

        # C. Opportunities count check
        opp_count = len(opportunities)
        if opp_count > 5:
            score += 30
            factors.append({"factor": "opportunities_gt_5", "points": 30, "detail": f"Discovered {opp_count} opportunities"})
        elif opp_count > 2:
            score += 20
            factors.append({"factor": "opportunities_gt_2", "points": 20, "detail": f"Discovered {opp_count} opportunities"})
        else:
            factors.append({"factor": "opportunities_low", "points": 0, "detail": f"Discovered {opp_count} opportunities"})

        # D. Critical opportunity match
        has_critical = any(o.get("priority") == "CRITICAL" for o in opportunities)
        if has_critical:
            score += 10
            factors.append({"factor": "has_critical_opportunity", "points": 10, "detail": "Contains critical priority recommendations"})

        # Clamp score between 0 and 100
        final_score = max(0, min(100, score))

        # E. Map Lead Grade
        if final_score >= 70:
            grade = LeadGrade.HOT
        elif final_score >= 40:
            grade = LeadGrade.WARM
        else:
            grade = LeadGrade.COLD

        # F. Map Routing path
        if grade == LeadGrade.HOT and (team >= 20 or leads >= 500):
            routing = RoutingPath.ENTERPRISE
        elif grade in [LeadGrade.HOT, LeadGrade.WARM]:
            routing = RoutingPath.CONSULTATION
        else:
            routing = RoutingPath.SELF_SERVE

        return QualificationResult(
            session_id=profile.session_id,
            qualification_score=final_score,
            lead_grade=grade,
            routing_path=routing,
            factors=factors,
            qualification_version=qualification_version
        )
