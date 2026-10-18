"""Communication Agent coordinator for message refinement and call briefing preparation."""

from typing import Any, Dict, List, Optional
from app.services.communication.providers import BaseCommunicationProvider, MockCommunicationProvider


class CommunicationAgent:
    """Agent orchestrating email/SMS composition, call briefing preparation, and provider execution."""

    def __init__(self, provider: Optional[BaseCommunicationProvider] = None):
        self._provider = provider or MockCommunicationProvider()

    @property
    def provider(self) -> BaseCommunicationProvider:
        return self._provider

    def refine_message(
        self,
        channel: str,
        recipient: str,
        body: str,
        subject: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate and refine drafted message content."""
        clean_body = body.strip()
        clean_subject = subject.strip() if subject else None
        if channel.upper() == "EMAIL" and not clean_subject:
            clean_subject = "Important Update from JARVIS"

        return {
            "channel": channel.upper(),
            "recipient": recipient.strip(),
            "subject": clean_subject,
            "body": clean_body,
        }

    def prepare_call_briefing(
        self,
        recipient_phone: str,
        purpose: str,
        briefing_notes: Optional[str] = None,
        recipient_name: Optional[str] = None,
    ) -> str:
        """Format a structured call agenda and briefing dossier."""
        name_str = f" with {recipient_name}" if recipient_name else ""
        default_agenda = "1. State purpose of call\n2. Address primary inquiries\n3. Confirm action items and follow-up timeline"
        agenda_text = briefing_notes or default_agenda
        notes = (
            f"# Outbound Call Briefing{name_str}\n"
            f"- **Target Phone:** {recipient_phone}\n"
            f"- **Core Purpose:** {purpose}\n"
            "- **Compliance:** Mandatory recording consent disclosure active.\n\n"
            "## Key Agenda Items:\n"
            f"{agenda_text}"
        )
        return notes

    async def execute_send(
        self,
        channel: str,
        recipient: str,
        subject: Optional[str],
        body: str,
    ) -> Dict[str, Any]:
        """Dispatch message via active communication provider."""
        return await self._provider.send_message(
            channel=channel,
            recipient=recipient,
            subject=subject,
            body=body,
        )

    async def execute_call(
        self,
        recipient_phone: str,
        purpose: str,
        briefing_notes: Optional[str],
        recording_consent_disclosed: bool,
    ) -> Dict[str, Any]:
        """Execute call via active provider."""
        return await self._provider.place_call(
            recipient_phone=recipient_phone,
            purpose=purpose,
            briefing_notes=briefing_notes,
            recording_consent_disclosed=recording_consent_disclosed,
        )
