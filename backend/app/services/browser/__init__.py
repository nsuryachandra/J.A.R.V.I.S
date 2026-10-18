"""Browser & Computer Agent domain service package."""

from app.services.browser.browser_agent import BrowserAgent
from app.services.browser.providers import (
    BaseBrowserProvider,
    HeadlessBrowserProvider,
    MockBrowserProvider,
)
from app.services.browser.schemas import (
    BrowserActionResponse,
    BrowserSessionSummary,
    CaptureScreenshotRequest,
    CreateBrowserSessionRequest,
    FillFormRequest,
    FillFormResponse,
    NavigateRequest,
    NavigateResponse,
    PageElementInfo,
    ReadPageResponse,
    ScreenshotResponse,
    SubmitFormRequest,
    SubmitFormResponse,
)
from app.services.browser.security import BrowserSecurityValidator
from app.services.browser.service import BrowserService

__all__ = [
    "BrowserService",
    "BrowserAgent",
    "BaseBrowserProvider",
    "MockBrowserProvider",
    "HeadlessBrowserProvider",
    "BrowserSecurityValidator",
    "CreateBrowserSessionRequest",
    "BrowserSessionSummary",
    "NavigateRequest",
    "NavigateResponse",
    "PageElementInfo",
    "ReadPageResponse",
    "FillFormRequest",
    "FillFormResponse",
    "SubmitFormRequest",
    "SubmitFormResponse",
    "CaptureScreenshotRequest",
    "ScreenshotResponse",
    "BrowserActionResponse",
]
