import os
import httpx
import logging
from typing import Dict, Any, List, Tuple
from app.domain.entities.profile import BusinessProfile
from app.domain.policies.narrative import NarrativeValidationPolicy

logger = logging.getLogger("tvira.grok_service")

class GrokNarrativeService:
    """Invokes the Grok narrative layer (with a reliable local fallback if xAI API keys are missing)."""

    async def generate_narrative(
        self,
        structured_report: Dict[str, Any],
        profile: BusinessProfile,
        evidence: List[Dict[str, Any]]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Generates the report explanation text and returns narrative-to-evidence links.
        - Paragraph 0 is mapped to scale (monthly_leads).
        - Paragraph 1 is mapped to operational complexity / channels.
        """
        api_key = os.environ.get("XAI_API_KEY")
        narrative = ""
        
        # 1. Attempt Live Grok Call if API key exists
        if api_key:
            try:
                narrative = await self._call_grok_api(api_key, structured_report)
                # Run hallucination validation
                is_valid, validation_errors = NarrativeValidationPolicy.validate_narrative(narrative, profile, evidence)
                
                if not is_valid:
                    logger.warning(f"Grok validation failed, applying fallback: {validation_errors}")
                    narrative = "" # Reset to force fallback
            except Exception as e:
                logger.error(f"Failed calling Grok API: {e}. Falling back to local template.")
                narrative = ""

        # 2. Local Fallback Template Engine (Always active in dev/testing)
        if not narrative:
            narrative = self._generate_local_fallback_narrative(structured_report, profile)

        # 3. Compile Narrative-to-Evidence paragraph mapping
        # Maps Paragraph 0 to lead volume/scale evidence, and Paragraph 1 to communication/ops evidence
        evidence_mapping = []
        
        # Find leads evidence id
        leads_evidence_id = None
        channels_evidence_id = None
        for ev in evidence:
            if ev.get("field") == "monthly_leads":
                leads_evidence_id = ev.get("id")
            elif ev.get("field") == "communication_channels":
                channels_evidence_id = ev.get("id")

        if leads_evidence_id:
            evidence_mapping.append({
                "paragraph_index": 0,
                "evidence_id": leads_evidence_id,
                "fields": ["monthly_leads"]
            })
        if channels_evidence_id:
            evidence_mapping.append({
                "paragraph_index": 1,
                "evidence_id": channels_evidence_id,
                "fields": ["communication_channels"]
            })

        return narrative, evidence_mapping

    async def _call_grok_api(self, api_key: str, structured_report: Dict[str, Any]) -> str:
        """Invokes the xAI Grok API endpoint."""
        url = "https://api.x.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        system_prompt = (
            "You are a Senior Business Consultant for Tvira Business. "
            "Translate the provided structured report JSON into a professional, human-friendly summary narrative. "
            "Strictly write exactly two paragraphs: "
            "1. Discuss lead volume and business growth constraints. "
            "2. Discuss operations, manual communication channels, and automation opportunities. "
            "Do NOT invent or hallucinate metrics. Rely only on values present in the JSON. "
            "Keep the language consultative, professional, and clear."
        )

        payload = {
            "model": "grok-beta",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Structured Report JSON:\n{structured_report}"}
            ],
            "temperature": 0.3
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=15.0)
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                logger.error(f"Grok API error: {response.status_code} - {response.text}")
                raise Exception("Grok API response failed.")

    def _generate_local_fallback_narrative(
        self, structured_report: Dict[str, Any], profile: BusinessProfile
    ) -> str:
        """Compiles clean, deterministic business summaries grounded in profile facts."""
        leads = profile.monthly_leads or 0
        team = profile.team_size or 0
        biz_type = profile.business_type or "company"
        channels = ", ".join(profile.communication_channels) if profile.communication_channels else "manual channels"

        # Paragraph 1: Scale constraint story
        p1 = (
            f"Based on the analysis of your {biz_type} operations, managing a volume of {leads} inquiries "
            f"monthly represents a substantial administrative overhead. Without structured automation, "
            f"your lead capture pipeline is susceptible to response delays, causing potential customer drop-offs "
            f"before qualification."
        )

        # Paragraph 2: Operational automation opportunities
        p2 = (
            f"Your team of {team} is currently coordinating customer touchpoints across {channels}. "
            f"Transitioning to automated routing and deploying scheduling scripts can significantly reduce "
            f"manual transcription tasks, freeing counselor and broker resources for direct sales conversion."
        )

        return f"{p1}\n\n{p2}"
