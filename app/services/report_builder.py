from typing import List, Dict, Any
from app.domain.entities.profile import BusinessProfile
from app.domain.value_objects.report import PriorityQuadrant

class ReportBuilder:
    """Builder service responsible for compiling the structured report data source of truth."""

    @staticmethod
    def build_structured_report(
        profile: BusinessProfile,
        context_facts: Dict[str, Any],
        opportunity_results: List[Dict[str, Any]],
        health_scores: Dict[str, int]
    ) -> Dict[str, Any]:
        """Assembles the executive priority matrix and outputs structured report context."""
        
        # 1. Compile Priority Matrix Quadrants
        quick_wins = []
        strategic_projects = []
        secondary_focus = []
        long_term_initiatives = []

        for opp in opportunity_results:
            impact = opp.get("impact", 50)
            complexity = opp.get("complexity", 50)
            code = opp.get("template_code", "UNKNOWN")
            
            # Retrieve display name from seed list mappings or default
            name_map = {
                "AI_RECEPTIONIST": "AI Receptionist Chatbot",
                "CRM_AUTOMATION": "CRM & Lead Routing System",
                "APPOINTMENT_SCHEDULING": "Automated Appointment Scheduling"
            }
            name = name_map.get(code, code.replace("_", " ").title())
            
            item = {"code": code, "name": name, "impact": impact, "complexity": complexity}

            if impact >= 60 and complexity <= 40:
                quick_wins.append(item)
            elif impact >= 60 and complexity > 40:
                strategic_projects.append(item)
            elif impact < 60 and complexity > 40:
                long_term_initiatives.append(item)
            else:
                secondary_focus.append(item)

        # 2. Extract Key Challenges (Risks)
        risks = []
        for p in profile.pain_points:
            risks.append(f"Pain Point Identified: {p}")
        if health_scores.get("automation_health", 100) < 50:
            risks.append("Low overall automation coverage creates operational drag.")
        if health_scores.get("communication_health", 100) < 60:
            risks.append("Siloed customer channels expose leads to leakage and response delays.")

        # 3. Generate Recommended Next Steps
        recommended_actions = []
        # Priority actions based on Quick Wins
        for qw in quick_wins:
            recommended_actions.append(f"Immediate Implementation: Deploy {qw['name']} (High Impact, Low Complexity)")
        for sp in strategic_projects:
            recommended_actions.append(f"Project Scoping: Map requirements for {sp['name']}")

        # Fallback action
        if not recommended_actions:
            recommended_actions.append("Conduct an operations audit to outline specific automation candidates.")

        return {
            "executive_summary_data": {
                "industry": profile.industry or "Generic",
                "business_type": profile.business_type or "Generic",
                "team_size": profile.team_size or 1,
                "monthly_leads": profile.monthly_leads or 0,
                "monthly_customers": profile.monthly_customers or 0,
            },
            "business_snapshot": {
                "stage": profile.business_stage or "STARTUP",
                "communication_channels": profile.communication_channels,
                "health_metrics": health_scores
            },
            "priority_matrix": {
                "quick_wins": quick_wins,
                "strategic_projects": strategic_projects,
                "long_term_initiatives": long_term_initiatives,
                "secondary_focus": secondary_focus
            },
            "risks": risks,
            "recommended_actions": recommended_actions
        }
