from app.domain.entities.profile import BusinessProfile

class ProfileCompletionPolicy:
    """Policy to determine completeness and readiness of a BusinessProfile."""
    
    @staticmethod
    def calculate_percentage(profile: BusinessProfile) -> float:
        """Calculates completion rate dynamically."""
        return profile.calculate_completion()

    @staticmethod
    def is_ready_for_analysis(profile: BusinessProfile) -> bool:
        """Determines if the critical minimum fields are filled to transition to analysis.
        Minimum requirements: business_type, industry, monthly_leads, team_size.
        """
        critical_fields = [
            profile.business_type,
            profile.industry,
            profile.team_size,
            profile.monthly_leads
        ]
        return all(field is not None for field in critical_fields)
