import re
from typing import List, Tuple, Dict, Any
from app.domain.entities.profile import BusinessProfile

class NarrativeValidationPolicy:
    """Validates that Grok's narrative summaries remain grounded in profile evidence."""

    @staticmethod
    def validate_narrative(
        narrative: str,
        profile: BusinessProfile,
        evidence: List[Dict[str, Any]]
    ) -> Tuple[bool, List[str]]:
        """Scans the text for numbers and facts and cross-references them with evidence to prevent hallucinations."""
        errors = []
        if not narrative:
            return True, []

        # 1. Extract all numbers from the text
        text_numbers = [int(n) for n in re.findall(r"\b\d+\b", narrative)]
        
        # Gather all valid profile numbers
        valid_numbers = {
            profile.team_size,
            profile.monthly_leads,
            profile.monthly_customers
        }
        # Filter out None values
        valid_numbers = {n for n in valid_numbers if n is not None}
        # Add values from evidence list just in case
        for ev in evidence:
            val = ev.get("value")
            if isinstance(val, int):
                valid_numbers.add(val)

        # We allow standard writing numbers like 1, 2, 3, 4, 5, 100 (for percentages), 6 (six months), 24 (hours)
        allowed_constants = {1, 2, 3, 4, 5, 6, 24, 100, 2026, 2027}
        
        for num in text_numbers:
            if num not in valid_numbers and num not in allowed_constants:
                errors.append(f"Potential hallucinated metric found in narrative: '{num}'")

        # 2. Check channel names mentioned
        lower_narrative = narrative.lower()
        channels = ["whatsapp", "email", "instagram", "facebook", "sms", "website"]
        
        for channel in channels:
            if channel in lower_narrative:
                # If mentioned, it must be in the profile's channels
                profile_channels_lower = [c.lower() for c in profile.communication_channels]
                # Fallback: if the profile has no channels yet, or does not contain it, it might be a hallucination
                if channel not in profile_channels_lower:
                    # Check if it was a negative mention like "not using instagram"
                    # But for strict grounding, warn about it:
                    errors.append(f"Channel '{channel.capitalize()}' is mentioned in narrative but not in profile channels.")

        # Filter warnings: if we have more than 3 mismatch warnings, mark as invalid
        is_valid = len(errors) == 0
        return is_valid, errors
