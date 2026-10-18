"""Pydantic schemas and contracts for Communication & Calls: Messages and Telephony."""

import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CreateMessageDraftRequest(BaseModel):
    """Payload to draft an outbound email, SMS, or chat message."""

    channel: str = Field(default="EMAIL", description="'EMAIL', 'SMS', or 'CHAT_MESSAGE'")
    recipient: str = Field(min_length=1, max_length=255, description="Email address, phone number, or handle")
    subject: Optional[str] = Field(default=None, max_length=255, description="Subject line for email")
    body: str = Field(min_length=1, description="Message body content")


class MessageDraftResponse(BaseModel):
    """Structured response for a message draft."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    channel: str
    recipient: str
    subject: Optional[str] = None
    body: str
    status: str
    approval_id: Optional[uuid.UUID] = None
    sent_at: Optional[str] = None
    created_at: str
    updated_at: str


class SendMessageRequest(BaseModel):
    """Payload to execute consequential message dispatch with Policy Broker authorization."""

    approval_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Authorization approval token ID granting permission to dispatch",
    )


class SendMessageResponse(BaseModel):
    """Result of message dispatch attempt."""

    draft_id: uuid.UUID
    status: str
    sent_at: Optional[str] = None
    message: str


class PlanCallRequest(BaseModel):
    """Payload to prepare and plan a telephony call briefing."""

    recipient_phone: str = Field(min_length=1, max_length=64, description="Target phone number (e.g. +1234567890)")
    recipient_name: Optional[str] = Field(default=None, max_length=255)
    purpose: str = Field(min_length=1, max_length=255, description="Objective of call")
    briefing_notes: Optional[str] = Field(default=None, description="Detailed agenda, key talking points, questions")
    recording_consent_disclosed: bool = Field(
        default=True,
        description="Confirmation that recording/transcription consent notice will be played",
    )


class CallSessionResponse(BaseModel):
    """Structured representation of a planned or executed call session."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    recipient_phone: str
    recipient_name: Optional[str] = None
    purpose: str
    briefing_notes: Optional[str] = None
    recording_consent_disclosed: bool
    status: str
    transcript: Optional[str] = None
    call_summary: Optional[str] = None
    approval_id: Optional[uuid.UUID] = None
    duration_seconds: int
    created_at: str
    updated_at: str


class InitiateCallRequest(BaseModel):
    """Payload to dial out call under consequential approval gate."""

    approval_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Approval token ID granting permission to initiate call",
    )


class InitiateCallResponse(BaseModel):
    """Result of call initiation."""

    call_id: uuid.UUID
    status: str
    transcript: Optional[str] = None
    call_summary: Optional[str] = None
    message: str
