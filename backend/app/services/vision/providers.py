"""Multimodal Vision providers: Abstract interface, deterministic offline mock, and NVIDIA NIM integration."""

import abc
import base64
import json
from typing import Any, Dict, List, Optional
from app.core.config import get_settings


class BaseVisionProvider(abc.ABC):
    """Abstract interface for multimodal vision and screen frame analysis."""

    @abc.abstractmethod
    async def analyze_image(
        self,
        image_bytes: bytes,
        media_type: str,
        prompt: str,
    ) -> Dict[str, Any]:
        """Analyze visual frame and return structured reasoning, OCR, and detected entities."""
        pass


class MockVisionProvider(BaseVisionProvider):
    """Deterministic offline mock vision provider for testing and sandboxed execution.

    Requires zero external network requests and produces reliable, reproducible visual analysis.
    """

    def __init__(self, model_name: str = "mock-vision-v1"):
        self.model_name = model_name

    async def analyze_image(
        self,
        image_bytes: bytes,
        media_type: str,
        prompt: str,
    ) -> Dict[str, Any]:
        """Analyze image bytes with deterministic heuristic pattern matching."""
        prompt_lower = (prompt or "").lower()
        byte_len = len(image_bytes)

        detected_objects: List[str] = []
        ocr_text: Optional[str] = None

        if "ocr" in prompt_lower or "text" in prompt_lower or "extract" in prompt_lower:
            ocr_text = (
                "JARVIS Multimodal OCR Engine\n"
                "Document Header: Quarterly Performance & System Health\n"
                "Status: 100% Operational | Latency: 12ms | Throughput: 4,800 req/s\n"
                "Approved By: Security Oversight Policy Broker"
            )
            detected_objects = ["text_block", "document_header", "table_row"]
            analysis = (
                f"High-fidelity OCR extraction completed ({media_type}, {byte_len} bytes). "
                "Document contains structured performance metrics and policy approval confirmations."
            )
        elif "screen" in prompt_lower or "window" in prompt_lower or "ui" in prompt_lower:
            ocr_text = "Active Window: Terminal & Code Editor\nButton: [Commit Changes]\nStatus: Ready"
            detected_objects = ["window_frame", "editor_panel", "button_primary", "status_indicator"]
            analysis = (
                "Screen capture analysis identified a desktop workstation layout with an active IDE editor, "
                "terminal dashboard, and interactive confirmation controls."
            )
        elif "camera" in prompt_lower or "face" in prompt_lower or "room" in prompt_lower:
            detected_objects = ["person", "workspace_desk", "laptop_device", "monitor"]
            ocr_text = None
            analysis = (
                "Camera stream analysis identified an authenticated user seated at a personal workstation "
                "with ambient office lighting and privacy-safe background."
            )
        else:
            detected_objects = ["visual_element", "interface_card"]
            ocr_text = "Sample Headline: Multimodal Vision Ready"
            analysis = (
                f"Multimodal image inspection verified valid {media_type} frame ({byte_len} bytes). "
                "Identified primary visual subject, balanced contrast, and clear structural hierarchy."
            )

        return {
            "analysis_result": analysis,
            "ocr_text": ocr_text,
            "detected_objects": detected_objects,
            "model_used": self.model_name,
        }


class NvidiaVisionProvider(BaseVisionProvider):
    """NVIDIA NIM Multimodal Vision integration with fallback to MockVisionProvider."""

    def __init__(self, fallback_provider: Optional[BaseVisionProvider] = None):
        self._fallback = fallback_provider or MockVisionProvider(model_name="mock-vision-fallback")
        self._settings = get_settings()

    async def analyze_image(
        self,
        image_bytes: bytes,
        media_type: str,
        prompt: str,
    ) -> Dict[str, Any]:
        """Send image to NVIDIA NIM vision API if API key is present, else use fallback."""
        if not self._settings.nvidia_api_key or self._settings.use_mock_models:
            return await self._fallback.analyze_image(image_bytes, media_type, prompt)

        # In live cloud environment with valid key, call NVIDIA NIM multimodal endpoint
        try:
            import httpx

            b64_img = base64.b64encode(image_bytes).decode("utf-8")
            payload = {
                "model": self._settings.model_vision,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{media_type};base64,{b64_img}"},
                            },
                        ],
                    }
                ],
                "max_tokens": 512,
                "temperature": 0.2,
            }
            async with httpx.AsyncClient(timeout=self._settings.model_timeout_seconds) as client:
                res = await client.post(
                    f"{self._settings.nvidia_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._settings.nvidia_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"]
                    return {
                        "analysis_result": content,
                        "ocr_text": None,
                        "detected_objects": ["multimodal_feature"],
                        "model_used": self._settings.model_vision,
                    }
                # On non-200, fallback gracefully
                return await self._fallback.analyze_image(image_bytes, media_type, prompt)
        except Exception:
            return await self._fallback.analyze_image(image_bytes, media_type, prompt)
