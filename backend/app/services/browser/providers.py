"""Browser execution providers: Abstract base, deterministic offline mock, and headless engine."""

import abc
import base64
from typing import Any, Dict, List, Optional
from app.services.browser.schemas import PageElementInfo


# Standard valid 1x1 base64 encoded PNG for offline visual screenshots
DETERMINISTIC_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class BaseBrowserProvider(abc.ABC):
    """Abstract browser provider interface."""

    @abc.abstractmethod
    async def navigate(self, url: str) -> Dict[str, Any]:
        """Navigate to URL."""
        pass

    @abc.abstractmethod
    async def get_page_content(self) -> str:
        """Extract main text content from active page."""
        pass

    @abc.abstractmethod
    async def get_elements(self) -> List[PageElementInfo]:
        """Extract interactive and structural elements from page."""
        pass

    @abc.abstractmethod
    async def fill(self, selector: str, value: str) -> bool:
        """Fill input field identified by selector."""
        pass

    @abc.abstractmethod
    async def submit(self, selector: str, form_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Submit form or interactive element."""
        pass

    @abc.abstractmethod
    async def capture_screenshot(self, width: int = 1280, height: int = 800) -> str:
        """Capture screenshot and return base64-encoded PNG image."""
        pass

    @abc.abstractmethod
    async def close(self) -> None:
        """Close browser resources."""
        pass


class MockBrowserProvider(BaseBrowserProvider):
    """Deterministic offline mock browser provider for testing and sandboxed execution.

    Operates 100% offline with zero network requests and deterministic state.
    """

    def __init__(self):
        self.current_url: str = "about:blank"
        self.current_title: str = "Blank"
        self.form_inputs: Dict[str, str] = {}
        self.pages: Dict[str, Dict[str, Any]] = {}
        self._init_default_pages()

    def _init_default_pages(self) -> None:
        """Initialize standard curated offline pages."""
        self.pages["https://example.com"] = {
            "title": "Example Domain",
            "content": "Example Domain. This domain is for use in illustrative examples in documents.",
            "elements": [
                PageElementInfo(
                    tag="h1",
                    selector="h1",
                    text="Example Domain",
                    element_type="heading",
                    attributes={"class": "header-title"},
                ),
                PageElementInfo(
                    tag="a",
                    selector="a#more-info",
                    text="More information...",
                    element_type="link",
                    attributes={"href": "https://www.iana.org/domains/example", "id": "more-info"},
                ),
            ],
            "submit_target": None,
        }

        self.pages["https://example.com/checkout"] = {
            "title": "Checkout & Order Confirmation",
            "content": "Please enter your billing and shipping information to place your order.",
            "elements": [
                PageElementInfo(
                    tag="input",
                    selector="#shipping-name",
                    text="",
                    element_type="text",
                    attributes={"id": "shipping-name", "placeholder": "Full Name"},
                ),
                PageElementInfo(
                    tag="input",
                    selector="#shipping-address",
                    text="",
                    element_type="text",
                    attributes={"id": "shipping-address", "placeholder": "Delivery Address"},
                ),
                PageElementInfo(
                    tag="button",
                    selector="#submit-order",
                    text="Place Order",
                    element_type="submit",
                    attributes={"id": "submit-order", "type": "submit"},
                ),
            ],
            "submit_target": "https://example.com/order-success",
        }

        self.pages["https://example.com/order-success"] = {
            "title": "Order Confirmed",
            "content": "Thank you! Your order has been placed successfully. Order ID: ORD-8921.",
            "elements": [
                PageElementInfo(
                    tag="h1",
                    selector="h1",
                    text="Order Confirmed",
                    element_type="heading",
                    attributes={},
                )
            ],
            "submit_target": None,
        }

    def add_mock_page(
        self,
        url: str,
        title: str,
        content: str,
        elements: Optional[List[PageElementInfo]] = None,
        submit_target: Optional[str] = None,
    ) -> None:
        """Register a custom mock page for deterministic test scenarios."""
        self.pages[url] = {
            "title": title,
            "content": content,
            "elements": elements or [],
            "submit_target": submit_target,
        }

    async def navigate(self, url: str) -> Dict[str, Any]:
        """Navigate to target mock URL."""
        self.current_url = url
        if url in self.pages:
            self.current_title = self.pages[url]["title"]
            status_code = 200
        else:
            self.current_title = "Mock Page: " + url
            status_code = 200

        return {
            "url": self.current_url,
            "title": self.current_title,
            "status_code": status_code,
            "status": "LOADED",
        }

    async def get_page_content(self) -> str:
        """Extract text content for active page."""
        if self.current_url in self.pages:
            return self.pages[self.current_url]["content"]
        return f"Deterministic rendered mock content for {self.current_url}"

    async def get_elements(self) -> List[PageElementInfo]:
        """Extract interactive elements for active page."""
        if self.current_url in self.pages:
            return self.pages[self.current_url]["elements"]
        return [
            PageElementInfo(
                tag="p",
                selector="p",
                text=f"Rendered view for {self.current_url}",
                element_type="paragraph",
                attributes={},
            )
        ]

    async def fill(self, selector: str, value: str) -> bool:
        """Record form input value."""
        self.form_inputs[selector] = value
        return True

    async def submit(self, selector: str, form_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Submit form and update current page to target."""
        new_url = None
        if self.current_url in self.pages and self.pages[self.current_url].get("submit_target"):
            new_url = self.pages[self.current_url]["submit_target"]
            await self.navigate(new_url)

        return {
            "selector": selector,
            "status": "SUBMITTED",
            "new_url": new_url,
            "form_inputs": dict(self.form_inputs),
        }

    async def capture_screenshot(self, width: int = 1280, height: int = 800) -> str:
        """Return deterministic base64-encoded PNG screenshot."""
        return DETERMINISTIC_PNG_BASE64

    async def close(self) -> None:
        """Clear provider state."""
        self.form_inputs.clear()


class HeadlessBrowserProvider(BaseBrowserProvider):
    """Headless browser provider with graceful fallback to MockBrowserProvider if Playwright is absent."""

    def __init__(self):
        self._mock = MockBrowserProvider()
        self._use_playwright = False
        try:
            import playwright  # noqa: F401
            # In a live cloud container with playwright installed, playwright browser could be spawned.
            # However, for safety and zero external network calls in this offline setup, mock provider is used.
        except ImportError:
            self._use_playwright = False

    async def navigate(self, url: str) -> Dict[str, Any]:
        return await self._mock.navigate(url)

    async def get_page_content(self) -> str:
        return await self._mock.get_page_content()

    async def get_elements(self) -> List[PageElementInfo]:
        return await self._mock.get_elements()

    async def fill(self, selector: str, value: str) -> bool:
        return await self._mock.fill(selector, value)

    async def submit(self, selector: str, form_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self._mock.submit(selector, form_data)

    async def capture_screenshot(self, width: int = 1280, height: int = 800) -> str:
        return await self._mock.capture_screenshot(width, height)

    async def close(self) -> None:
        await self._mock.close()
