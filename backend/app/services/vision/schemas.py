"""Pydantic schemas and contracts for Vision, Camera, & Screen multimodal operations."""

import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CreateVisionSessionRequest(BaseModel):
    """Payload to initiate a new vision inspection or streaming session."""

    title: Optional[str] = Field(default="Vision Inspection Session", max_length=255)
    session_type: str = Field(
        default="IMAGE_UPLOAD",
        description="Session modality: 'IMAGE_UPLOAD', 'SCREEN_SHARE', or 'CAMERA_STREAM'",
    )
    consent_granted: bool = Field(
        default=True,
        description="Explicit user consent confirming camera/screen/image processing",
    )
    device_info: Optional[str] = Field(default=None, max_length=255)


class VisionSessionSummary(BaseModel):
    """Summary representation of a vision session."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    session_type: str
    status: str
    privacy_indicator: bool
    consent_granted: bool
    device_info: Optional[str] = None
    frames_count: int = 0
    created_at: str
    updated_at: str


class TogglePrivacyRequest(BaseModel):
    """Payload to toggle capture privacy state."""

    action: str = Field(
        description="Privacy state command: 'MUTE', 'UNMUTE', or 'STOP'",
    )


class TogglePrivacyResponse(BaseModel):
    """Result of privacy toggle operation."""

    session_id: uuid.UUID
    status: str
    privacy_indicator: bool
    message: str


class AnalyzeFrameRequest(BaseModel):
    """Payload to ingest and analyze a captured or uploaded frame within a session."""

    image_base64: str = Field(description="Base64 encoded image frame data")
    media_type: str = Field(default="image/png", description="MIME type (image/png, image/jpeg, image/webp)")
    query_prompt: Optional[str] = Field(
        default="Describe what is shown in this image and extract any visible text.",
        max_length=1024,
    )
    width: Optional[int] = Field(default=1280, ge=10, le=4096)
    height: Optional[int] = Field(default=720, ge=10, le=4096)


class VisionFrameResponse(BaseModel):
    """Structured result of visual frame multimodal analysis."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    media_type: str
    width: int
    height: int
    size_bytes: int
    query_prompt: Optional[str] = None
    analysis_result: str
    ocr_text: Optional[str] = None
    detected_objects: List[str] = Field(default_factory=list)
    created_at: str


class StandaloneVisionAnalysisRequest(BaseModel):
    """Payload for single-shot direct image inspection without a persistent session."""

    image_base64: str = Field(description="Base64 encoded image frame data")
    media_type: str = Field(default="image/png", description="MIME type")
    query_prompt: Optional[str] = Field(
        default="Describe what is shown in this image and extract any visible text.",
        max_length=1024,
    )


class StandaloneVisionAnalysisResponse(BaseModel):
    """Direct visual inspection response."""

    analysis_result: str
    ocr_text: Optional[str] = None
    detected_objects: List[str] = Field(default_factory=list)
    model_used: str
