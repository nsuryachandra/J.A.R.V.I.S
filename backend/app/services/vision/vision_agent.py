"""Vision Agent coordinator handling frame validation, decoding, and provider analysis."""

from typing import Any, Dict, Optional, Tuple
from app.services.vision.providers import BaseVisionProvider, MockVisionProvider
from app.services.vision.validator import VisionValidator


class VisionAgent:
    """Agent orchestrating multimodal image inspection, screen frame interpretation, and OCR."""

    def __init__(self, provider: Optional[BaseVisionProvider] = None):
        self._provider = provider or MockVisionProvider()
        self._validator = VisionValidator()

    @property
    def provider(self) -> BaseVisionProvider:
        return self._provider

    async def process_and_analyze(
        self,
        image_base64: str,
        prompt: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], bytes, str]:
        """Validate base64 image data and run multimodal vision analysis."""
        image_bytes, media_type = self._validator.clean_and_decode_base64(image_base64)
        active_prompt = prompt or "Describe what is shown in this image and extract any visible text."

        analysis_dict = await self._provider.analyze_image(
            image_bytes=image_bytes,
            media_type=media_type,
            prompt=active_prompt,
        )

        return analysis_dict, image_bytes, media_type
