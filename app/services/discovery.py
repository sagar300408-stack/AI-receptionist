import re
import logging
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.entities.profile import BusinessProfile
from app.domain.value_objects.tiers import LeadVolumeTier, BusinessMaturity
from app.domain.events.base import ProfileUpdatedEvent
from app.services.event_bus import event_bus

logger = logging.getLogger("tvira.discovery")

class DiscoveryService:
    """Service governing natural text parsing and BusinessProfile mapping."""

    def parse_response(self, question_key: str, raw_answer: str) -> Dict[str, Any]:
        """Heuristic text extraction engine mapping natural language to profile variables."""
        parsed: Dict[str, Any] = {}
        
        # Clean answer for processing
        clean = raw_answer.strip()
        
        if question_key == "business_type":
            parsed["business_type"] = clean
            # Infer industry
            if any(w in clean.lower() for w in ["coach", "school", "teach", "institute", "learn"]):
                parsed["industry"] = "Coaching Institute"
            elif any(w in clean.lower() for w in ["real", "estate", "agent", "property", "broker"]):
                parsed["industry"] = "Real Estate"
            elif any(w in clean.lower() for w in ["store", "shop", "ecommerce", "buy", "sell"]):
                parsed["industry"] = "E-Commerce"
            else:
                parsed["industry"] = "Generic"
                
        elif question_key == "industry":
            parsed["industry"] = clean
            
        elif question_key == "team_size":
            # Extract number
            numbers = re.findall(r"\d+", clean)
            if numbers:
                val = int(numbers[-1]) # Default to upper range or single digit
                parsed["team_size"] = val
                # Infer stage
                if val <= 5:
                    parsed["business_stage"] = "STARTUP"
                elif val <= 50:
                    parsed["business_stage"] = "GROWTH"
                else:
                    parsed["business_stage"] = "MATURE"
            else:
                parsed["team_size"] = 1 # Fallback
                parsed["business_stage"] = "STARTUP"
                
        elif question_key == "monthly_leads":
            numbers = re.findall(r"\d+", clean)
            parsed["monthly_leads"] = int(numbers[-1]) if numbers else 0
            
        elif question_key == "monthly_customers":
            numbers = re.findall(r"\d+", clean)
            parsed["monthly_customers"] = int(numbers[-1]) if numbers else 0
            
        elif question_key == "communication_channels":
            channels = []
            lower = clean.lower()
            mapping = {
                "whatsapp": "WhatsApp",
                "email": "Email",
                "call": "Phone Call",
                "website": "Website",
                "instagram": "Instagram",
                "facebook": "Facebook",
                "sms": "SMS"
            }
            for key, display_name in mapping.items():
                if key in lower:
                    channels.append(display_name)
            if not channels:
                channels.append(clean)
            parsed["communication_channels"] = channels
            
        elif question_key == "pain_points":
            # Split by commas, bullet points or keep as list
            parts = [p.strip() for p in re.split(r"[,;.]", clean) if p.strip()]
            parsed["pain_points"] = parts if parts else [clean]
            
        elif question_key == "goals":
            parts = [p.strip() for p in re.split(r"[,;.]", clean) if p.strip()]
            parsed["goals"] = parts if parts else [clean]
            
        elif question_key == "business_stage":
            parsed["business_stage"] = clean

        return parsed

    async def apply_response_to_profile(
        self, db: AsyncSession, profile: BusinessProfile, question_key: str, raw_answer: str
    ) -> Dict[str, Any]:
        """Applies parsed answers, updates profile progress, and publishes domain events."""
        parsed_fields = self.parse_response(question_key, raw_answer)
        
        # Apply fields to domain entity
        for key, val in parsed_fields.items():
            profile.update_field(key, val)

        # Triggers progress calculation
        profile.calculate_completion()

        # Emit domain event for profile updates
        event = ProfileUpdatedEvent(
            session_id=profile.session_id,
            updated_fields=parsed_fields,
            completion=profile.profile_completion
        )
        await event_bus.publish(event)
        
        return parsed_fields

    def evaluate_business_context_facts(self, profile: BusinessProfile) -> Dict[str, Any]:
        """Calculates derived analytical facts from profile details (Business Context layer)."""
        facts = {}
        
        # Lead tier calculation
        leads = profile.monthly_leads or 0
        if leads >= 500:
            facts["lead_volume_tier"] = LeadVolumeTier.HIGH.value
        elif leads >= 100:
            facts["lead_volume_tier"] = LeadVolumeTier.MEDIUM.value
        else:
            facts["lead_volume_tier"] = LeadVolumeTier.LOW.value

        # Operational complexity mapping
        team = profile.team_size or 0
        channels = len(profile.communication_channels)
        if team > 20 or channels >= 4:
            facts["operational_complexity"] = "HIGH"
        elif team > 5 or channels >= 2:
            facts["operational_complexity"] = "MEDIUM"
        else:
            facts["operational_complexity"] = "LOW"

        # Maturity tier mapping
        if profile.business_stage:
            facts["business_maturity"] = profile.business_stage
        else:
            facts["business_maturity"] = BusinessMaturity.STARTUP.value

        return facts
