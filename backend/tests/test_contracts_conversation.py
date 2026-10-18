"""Tests for Conversation, Message, MessageContentPart, and AttachmentReference contracts."""

from datetime import datetime, timezone
import uuid
import pytest
from pydantic import ValidationError
from app.contracts.common import PrivacyScope, SensitivityLevel
from app.contracts.conversation import (
    AttachmentReference,
    ContentType,
    Conversation,
    ConversationParticipant,
    ConversationState,
    ConversationSummary,
    Message,
    MessageContentPart,
    MessageMetadata,
    MessageRole,
)


def test_attachment_reference_creation():
    """Verify AttachmentReference stores safe non-executable metadata."""
    att = AttachmentReference(
        content_type=ContentType.DOCUMENT_REF,
        filename="financial_summary.pdf",
        mime_type="application/pdf",
        size_bytes=10240,
        storage_uri="internal://vault/docs/financial_summary.pdf",
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    assert att.filename == "financial_summary.pdf"
    assert att.size_bytes == 10240
    assert len(att.sha256_hash) == 64


def test_message_content_part_validation():
    """Verify validation of TEXT vs attachment parts."""
    # TEXT requires text
    p_text = MessageContentPart(type=ContentType.TEXT, text="Hello Jarvis")
    assert p_text.text == "Hello Jarvis"

    with pytest.raises(ValidationError):
        # Empty text raises error
        MessageContentPart(type=ContentType.TEXT, text="")

    # IMAGE_REF requires attachment reference
    with pytest.raises(ValidationError):
        MessageContentPart(type=ContentType.IMAGE_REF)


def test_message_creation_and_utc_timestamp():
    """Verify message contract construction and UTC timestamp validation."""
    conv_id = uuid.uuid4()
    msg = Message(
        conversation_id=conv_id,
        role=MessageRole.USER,
        content_parts=[MessageContentPart(type=ContentType.TEXT, text="Remind me to buy groceries")],
        metadata=MessageMetadata(
            sensitivity=SensitivityLevel.PRIVATE,
            privacy_scope=PrivacyScope.PERSONAL,
        ),
    )
    assert msg.conversation_id == conv_id
    assert msg.role == MessageRole.USER
    assert msg.created_at_utc.tzinfo == timezone.utc


def test_conversation_session_lifecycle():
    """Verify Conversation container with participants and state."""
    uid = uuid.uuid4()
    cid = uuid.uuid4()
    p1 = ConversationParticipant(name="User", role=MessageRole.USER)
    p2 = ConversationParticipant(name="JARVIS", role=MessageRole.ASSISTANT)

    conv = Conversation(
        conversation_id=cid,
        user_id=uid,
        title="Weekly Planning",
        state=ConversationState.ACTIVE,
        participants=[p1, p2],
    )
    assert conv.user_id == uid
    assert conv.state == ConversationState.ACTIVE
    assert len(conv.participants) == 2


def test_conversation_summary():
    """Verify lightweight projection summary."""
    cid = uuid.uuid4()
    summary = ConversationSummary(
        conversation_id=cid,
        title="Project Discussion",
        state=ConversationState.ACTIVE,
        message_count=12,
        last_message_at_utc=datetime.now(timezone.utc),
    )
    assert summary.message_count == 12
    assert summary.state == ConversationState.ACTIVE
