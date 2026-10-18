"""Pydantic schemas and contracts for Browser & Computer Agent operations."""

import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CreateBrowserSessionRequest(BaseModel):
    """Payload to initiate a new browser interaction session."""

    title: Optional[str] = Field(default="Web Interaction Session", max_length=255)
    viewport_width: int = Field(default=1280, ge=320, le=3840)
    viewport_height: int = Field(default=800, ge=240, le=2160)


class BrowserSessionSummary(BaseModel):
    """Summary of a browser session."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    current_url: str
    status: str
    viewport_width: int
    viewport_height: int
    created_at: str
    updated_at: str


class NavigateRequest(BaseModel):
    """Payload to navigate browser to a given target URL."""

    url: str = Field(min_length=1, max_length=1024, description="Target URL")


class NavigateResponse(BaseModel):
    """Result of browser navigation."""

    session_id: uuid.UUID
    url: str
    title: str
    status_code: int = 200
    status: str = "LOADED"


class PageElementInfo(BaseModel):
    """Structured DOM element description."""

    tag: str
    selector: str
    text: Optional[str] = None
    element_type: Optional[str] = None
    attributes: Dict[str, str] = Field(default_factory=dict)


class ReadPageResponse(BaseModel):
    """Extracted structured content and elements from current active page."""

    session_id: uuid.UUID
    url: str
    title: str
    content: str = Field(description="Sanitized content wrapped in <untrusted_content> tags")
    raw_text: str = Field(description="Raw text content extracted from DOM")
    elements: List[PageElementInfo] = Field(default_factory=list)


class FillFormRequest(BaseModel):
    """Payload to fill an interactive form input field."""

    selector: str = Field(min_length=1, max_length=255)
    value: str = Field(description="Value to fill into the input")


class FillFormResponse(BaseModel):
    """Result of form input operation."""

    session_id: uuid.UUID
    selector: str
    value: str
    success: bool = True
    status: str = "FILLED"


class SubmitFormRequest(BaseModel):
    """Payload to submit an interactive form (Consequential action)."""

    selector: str = Field(min_length=1, max_length=255)
    form_data: Optional[Dict[str, Any]] = None
    approval_id: Optional[uuid.UUID] = None


class SubmitFormResponse(BaseModel):
    """Result of form submission or policy approval gate response."""

    session_id: uuid.UUID
    selector: str
    status: str
    new_url: Optional[str] = None
    requires_approval: bool = False
    approval_request_id: Optional[uuid.UUID] = None
    message: Optional[str] = None


class CaptureScreenshotRequest(BaseModel):
    """Payload to capture visual screenshot."""

    caption: Optional[str] = Field(default=None, max_length=255)


class ScreenshotResponse(BaseModel):
    """Visual screenshot log record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    action_id: Optional[uuid.UUID] = None
    url: str
    image_base64: str
    width: int
    height: int
    caption: Optional[str] = None
    created_at: str


class BrowserActionResponse(BaseModel):
    """Recorded browser action entry."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    action_type: str
    target_selector: Optional[str] = None
    value: Optional[str] = None
    status: str
    approval_id: Optional[uuid.UUID] = None
    created_at: str
