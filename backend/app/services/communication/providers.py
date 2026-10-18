"""Communication providers: Abstract interface and deterministic offline mock provider."""

import abc
import uuid
from typing import Any, Dict, List, Optional
from app.core.exceptions import ValidationError


class BaseCommunicationProvider(abc.ABC):
    """Abstract interface for email, SMS, and telephony communications."""

    @abc.abstractmethod
    async def send_message(
        self,
        channel: str,
        recipient: str,
        subject: Optional[str],
        body: str,
    ) -> Dict[str, Any]:
        """Dispatch outbound message."""
        pass

    @abc.abstractmethod
    async def place_call(
        self,
        recipient_phone: str,
        purpose: str,
        briefing_notes: Optional[str],
        recording_consent_disclosed: bool,
    ) -> Dict[str, Any]:
        """Initiate outbound phone call with recording consent disclosure."""
        pass


class MockCommunicationProvider(BaseCommunicationProvider):
    """Deterministic offline mock communication provider.

    Executes 100% offline with zero external network requests.
    """

    def __init__(self):
        self.sent_messages: List[Dict[str, Any]] = []
        self.placed_calls: List[Dict[str, Any]] = []

    async def send_message(
        self,
        channel: str,
        recipient: str,
        subject: Optional[str],
        body: str,
    ) -> Dict[str, Any]:
        """Record dispatched mock message."""
        message_id = f"mock-msg-{uuid.uuid4().hex[:8]}"
        payload = {
            "message_id": message_id,
            "channel": channel.upper(),
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "status": "DELIVERED",
        }
        self.sent_messages.append(payload)
        return payload

    async def place_call(
        self,
        recipient_phone: str,
        purpose: str,
        briefing_notes: Optional[str],
        recording_consent_disclosed: bool,
    ) -> Dict[str, Any]:
        """Record and simulate completed mock telephony call."""
        if not recording_consent_disclosed:
            raise ValidationError(
                "Telephony compliance policy requires recording and transcription consent disclosure notice."
            )

        call_id = f"mock-call-{uuid.uuid4().hex[:8]}"
        simulated_transcript = (
            f"[Automated Consent Notice]: This call is recorded for transcription and quality assurance.\n"
            f"[JARVIS Agent]: Hello, I am calling on behalf of the user regarding: {purpose}.\n"
            f"[Recipient]: Hello, thank you for reaching out. Let me address those points.\n"
            f"[Briefing Reference]: Discussed {briefing_notes or 'key objectives'}.\n"
            f"[JARVIS Agent]: Thank you for your time. Have a great day."
        )
        simulated_summary = (
            f"Call completed with {recipient_phone} on '{purpose}'. "
            "Recording consent was acknowledged. Key talking points and agenda items addressed successfully."
        )

        payload = {
            "call_id": call_id,
            "recipient_phone": recipient_phone,
            "purpose": purpose,
            "status": "COMPLETED",
            "duration_seconds": 120,
            "transcript": simulated_transcript,
            "call_summary": simulated_summary,
        }
        self.placed_calls.append(payload)
        return payload
