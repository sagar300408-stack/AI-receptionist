from typing import List, Dict, Any
from app.domain.entities.profile import BusinessProfile
from app.domain.entities.health import BusinessHealthAssessment

class HealthAssessmentPolicy:
    """Evaluates the business health scores dimensions dynamically."""

    @staticmethod
    def assess_health(
        profile: BusinessProfile,
        opportunities: List[Dict[str, Any]],
        context_facts: Dict[str, Any],
        health_assessment_version: str = "1.0"
    ) -> BusinessHealthAssessment:
        """Calculates sub-scores (0-100) for core business dimensions."""
        
        # 1. Communication Health (Base 100)
        comm = 100
        comm_channels = [c.lower() for c in profile.communication_channels]
        
        if "whatsapp" not in comm_channels:
            comm -= 20
        if len(comm_channels) <= 1:
            comm -= 15
            
        lower_pains = [p.lower() for p in profile.pain_points]
        if any(w in p for p in lower_pains for w in ["communication", "followup", "delays", "phone"]):
            comm -= 15
            
        comm_health = max(10, min(100, comm))

        # 2. Automation Health (Base 100)
        # Outstanding opportunities count indicates gaps in current automated systems
        opp_deductions = len(opportunities) * 15
        auto_health = max(20, min(100, 100 - opp_deductions))

        # 3. Operational Health (Base 100)
        ops = 100
        team = profile.team_size or 0
        if team > 20:
            ops -= 20
        elif team > 5:
            ops -= 10
            
        if any(w in p for p in lower_pains for w in ["manual", "spreadsheet", "typing", "entry"]):
            ops -= 25
            
        ops_health = max(10, min(100, ops))

        # 4. Growth Readiness (Base 100)
        growth = 100
        leads = profile.monthly_leads or 0
        
        # High leads influx with poor automation level implies a operational choke point
        if leads >= 500 and auto_health < 50:
            growth -= 30
        elif leads < 50:
            # Under-performing lead channels
            growth -= 15
            
        growth_readiness = max(10, min(100, growth))

        facts = {
            "channels_count": len(profile.communication_channels),
            "team_size": team,
            "leads_count": leads,
            "opportunities_count": len(opportunities)
        }

        return BusinessHealthAssessment(
            session_id=profile.session_id,
            communication_health=comm_health,
            automation_health=auto_health,
            operational_health=ops_health,
            growth_readiness=growth_readiness,
            facts=facts,
            health_assessment_version=health_assessment_version
        )
