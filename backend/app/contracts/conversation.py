"""Structured conversation, message, attachment, and participant contracts."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.contracts.common import (
    PrivacyScope,
    SensitivityLevel,
    SourceReference,
    SourceType,
    UserScopedResource,
    VersionedContract,
)


class MessageRole(str, Enum):
    """Originating persona of a message in a conversational exchange."""

    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"
    TOOL = "TOOL"
    AGENT = "AGENT"


class ContentType(str, Enum):
    """Categorical format of a message content part."""

    TEXT = "TEXT"
    IMAGE_REF = "IMAGE_REF"
    AUDIO_REF = "AUDIO_REF"
    DOCUMENT_REF = "DOCUMENT_REF"
    TOOL_RESULT_REF = "TOOL_RESULT_REF"
    SYSTEM_EVENT_REF = "SYSTEM_EVENT_REF"


class AttachmentReference(BaseModel):
    """Safe, non-executable metadata reference to an external media object or artifact."""

    model_config = ConfigDict(frozen=True)

    attachment_id: UUID = Field(default_factory=uuid4)
    content_type: ContentType
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=3, max_length=128)
    size_bytes: int = Field(ge=0)
    storage_uri: str = Field(description="Storage URI or internal artifact path")
    sha256_hash: str = Field(min_length=64, max_length=64, description="Integrity digest")


class MessageContentPart(BaseModel):
    """Discrete atomic fragment of a message body (e.g. text segment or attachment reference)."""

    model_config = ConfigDict(frozen=True)

    type: ContentType
    text: Optional[str] = None
    attachment: Optional[AttachmentReference] = None

    @model_validator(mode="after")
    def validate_content_presence(self) -> "MessageContentPart":
        if self.type == ContentType.TEXT and not self.text:
            raise ValueError("TEXT content part must provide non-empty text")
        if self.type in (ContentType.IMAGE_REF, ContentType.AUDIO_REF, ContentType.DOCUMENT_REF) and not self.attachment:
            raise ValueError(f"{self.type} content part must provide an attachment reference")
        return self


class MessageMetadata(BaseModel):
    """Provenance, privacy classification, and routing metadata for a single message."""

    model_config = ConfigDict(frozen=True)

    source: SourceReference = Field(
        default_factory=lambda: SourceReference(source_type=SourceType.USER_DIRECT)
    )
    sensitivity: SensitivityLevel = Field(default=SensitivityLevel.PRIVATE)
    privacy_scope: PrivacyScope = Field(default=PrivacyScope.CONVERSATION)
    redacted: bool = Field(default=False)
    tokens_count: Optional[int] = Field(default=None, ge=0)


class Message(VersionedContract):
    """Immutable message record within a conversation exchange."""

    contract_type: str = Field(default="conversation.message")
    message_id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID
    role: MessageRole
    content_parts: List[MessageContentPart] = Field(min_length=1)
    metadata: MessageMetadata = Field(default_factory=MessageMetadata)
    created_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @field_validator("created_at_utc")
    @classmethod
    def validate_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("created_at_utc must be a timezone-aware UTC datetime")
        return v.astimezone(timezone.utc)


class ConversationState(str, Enum):
    """Lifecycle state of a conversation."""

    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ARCHIVED = "ARCHIVED"
    CLOSED = "CLOSED"


class ConversationParticipant(BaseModel):
    """Participant metadata in a conversation session."""

    model_config = ConfigDict(frozen=True)

    participant_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=128)
    role: MessageRole


class Conversation(UserScopedResource):
    """Parent container grouping related sequential messages under an authenticated user."""

    contract_type: str = Field(default="conversation.session")
    conversation_id: UUID = Field(default_factory=uuid4)
    title: str = Field(default="New Conversation", min_length=1, max_length=255)
    state: ConversationState = Field(default=ConversationState.ACTIVE)
    participants: List[ConversationParticipant] = Field(default_factory=list)
    privacy_scope: PrivacyScope = Field(default=PrivacyScope.CONVERSATION)
    sensitivity: SensitivityLevel = Field(default=SensitivityLevel.PRIVATE)


class ConversationSummary(BaseModel):
    """Lightweight projection of conversation state for navigation and index views."""

    model_config = ConfigDict(frozen=True)

    conversation_id: UUID
    title: str
    state: ConversationState
    message_count: int = Field(ge=0)
    last_message_at_utc: Optional[datetime] = None
