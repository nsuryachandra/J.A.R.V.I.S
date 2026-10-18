"""Browser agent coordinator handling web navigation, DOM parsing, and interaction sandboxing."""

from typing import Any, Dict, List, Optional
from app.services.browser.providers import BaseBrowserProvider, MockBrowserProvider
from app.services.browser.schemas import PageElementInfo
from app.services.browser.security import BrowserSecurityValidator


class BrowserAgent:
    """Agent orchestrating browser actions within safe sandbox boundaries."""

    def __init__(self, provider: Optional[BaseBrowserProvider] = None):
        self._provider = provider or MockBrowserProvider()
        self._security = BrowserSecurityValidator()

    @property
    def provider(self) -> BaseBrowserProvider:
        return self._provider

    async def navigate(self, url: str) -> Dict[str, Any]:
        """Validate URL and navigate safely."""
        clean_url = self._security.validate_url(url)
        return await self._provider.navigate(clean_url)

    async def read_page(self, url: str) -> Dict[str, Any]:
        """Extract text and elements from page, wrapping untrusted text in security delimiters."""
        raw_text = await self._provider.get_page_content()
        elements = await self._provider.get_elements()
        wrapped_content = self._security.wrap_untrusted_content(raw_text, url)

        return {
            "raw_text": raw_text,
            "wrapped_content": wrapped_content,
            "elements": elements,
        }

    async def fill_form(self, selector: str, value: str) -> bool:
        """Fill interactive form input."""
        return await self._provider.fill(selector, value)

    async def submit_form(self, selector: str, form_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Submit form through provider."""
        return await self._provider.submit(selector, form_data)

    async def capture_screenshot(self, width: int = 1280, height: int = 800) -> str:
        """Capture screenshot returning base64 PNG."""
        return await self._provider.capture_screenshot(width, height)

    async def close(self) -> None:
        """Close browser resources."""
        await self._provider.close()
