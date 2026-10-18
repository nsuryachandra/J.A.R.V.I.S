"""Live ElevenLabs API provider for high-quality speech synthesis."""

import asyncio
import logging
from typing import AsyncIterator, Optional, Tuple
import httpx
from app.core.config import get_settings
from app.services.voice.base import BaseVoiceProvider
from app.services.voice.schemas import VoiceProfile

logger = logging.getLogger(__name__)


class ElevenLabsProvider(BaseVoiceProvider):
    """ElevenLabs REST and streaming speech synthesis provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ):
        settings = get_settings()
        self.api_key = api_key or settings.elevenlabs_api_key
        self.base_url = (base_url or settings.elevenlabs_base_url).rstrip("/")
        self.timeout = float(timeout_seconds or settings.voice_timeout_seconds)
        self.model_id = settings.elevenlabs_model_id

    @property
    def provider_name(self) -> str:
        return "elevenlabs"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 0)

    def _headers(self, accept: str = "audio/mpeg") -> dict:
        return {
            "xi-api-key": self.api_key or "",
            "Accept": accept,
            "Content-Type": "application/json",
        }

    async def synthesize(
        self,
        text: str,
        profile: VoiceProfile,
        speed: float = 1.0,
        stability: float = 0.5,
        audio_format: str = "mp3",
    ) -> Tuple[bytes, float, str]:
        """Synthesize text via ElevenLabs REST API with exponential backoff retries."""
        if not self.is_configured:
            raise RuntimeError("ElevenLabs API key is not configured.")

        voice_id = profile.voice_id
        url = f"{self.base_url}/text-to-speech/{voice_id}"
        output_format = "mp3_44100_128" if audio_format.lower() == "mp3" else "pcm_16000"
        params = {"output_format": output_format}

        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": profile.similarity_boost,
                "style": profile.style,
                "use_speaker_boost": True,
            },
        }

        content_type = "audio/mpeg" if audio_format.lower() == "mp3" else "audio/wav"
        max_retries = 2
        delay = 1.0

        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        url,
                        headers=self._headers(accept=content_type),
                        params=params,
                        json=payload,
                    )

                    if resp.status_code == 200:
                        audio_data = resp.content
                        words = len(text.split()) if text else 1
                        duration = max(0.5, round(words / (2.5 * speed), 2))
                        return audio_data, duration, content_type

                    if resp.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                        logger.warning(
                            "ElevenLabs HTTP %d encountered, retrying in %.2fs (attempt %d/%d)",
                            resp.status_code,
                            delay,
                            attempt + 1,
                            max_retries,
                        )
                        await asyncio.sleep(delay)
                        delay *= 2.0
                        continue

                    resp.raise_for_status()

            except (httpx.TimeoutException, httpx.NetworkError) as err:
                if attempt < max_retries:
                    logger.warning("ElevenLabs network error (%s), retrying in %.2fs", str(err), delay)
                    await asyncio.sleep(delay)
                    delay *= 2.0
                    continue
                raise

        raise RuntimeError("ElevenLabs synthesis failed after retries.")

    async def stream(
        self,
        text: str,
        profile: VoiceProfile,
        speed: float = 1.0,
        stability: float = 0.5,
        audio_format: str = "mp3",
    ) -> AsyncIterator[bytes]:
        """Stream synthesized audio directly from ElevenLabs streaming endpoint."""
        if not self.is_configured:
            raise RuntimeError("ElevenLabs API key is not configured.")

        voice_id = profile.voice_id
        url = f"{self.base_url}/text-to-speech/{voice_id}/stream"
        output_format = "mp3_44100_128" if audio_format.lower() == "mp3" else "pcm_16000"
        params = {"output_format": output_format}

        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": profile.similarity_boost,
                "style": profile.style,
                "use_speaker_boost": True,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                url,
                headers=self._headers(accept="audio/mpeg"),
                params=params,
                json=payload,
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    if chunk:
                        yield chunk
