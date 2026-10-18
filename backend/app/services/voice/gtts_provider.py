"""Open-source natural human tone voice provider powered by gTTS with multi-language & regional accent support."""

import asyncio
import io
import logging
from typing import AsyncIterator, Tuple
from gtts import gTTS
from app.services.voice.base import BaseVoiceProvider
from app.services.voice.schemas import VoiceProfile

logger = logging.getLogger(__name__)


class OpenSourceVoiceProvider(BaseVoiceProvider):
    """Open-source, studio-grade neural voice provider with multi-language & accent support."""

    @property
    def provider_name(self) -> str:
        return "opensource"

    @property
    def is_configured(self) -> bool:
        return True

    def _resolve_lang_and_tld(self, text: str, profile: VoiceProfile) -> Tuple[str, str]:
        """Resolve appropriate language code and top-level domain for regional accent."""
        lower_text = text.lower()
        locale = (profile.locale or "en-IN").lower()

        # Detect Telugu or Tenglish
        if any(w in lower_text for w in ["ela unnaru", "bagunnara", "namaskaram", "nenu", "meeru", "chala bagunnanu", "em chestunnav"]) or "te" in locale:
            # If purely Telugu script, use 'te'; otherwise Indian English accent for Tenglish
            if any("\u0c00" <= ch <= "\u0c7f" for ch in text):
                return "te", "co.in"
            return "en", "co.in"

        # Detect Hindi
        if any(w in lower_text for w in ["namaste", "kaise ho", "kya haal", "theek"]) or "hi" in locale:
            if any("\u0900" <= ch <= "\u097f" for ch in text):
                return "hi", "co.in"
            return "en", "co.in"

        # Indian English
        if "in" in locale:
            return "en", "co.in"

        # British J.A.R.V.I.S.
        if "gb" in locale or "uk" in locale:
            return "en", "co.uk"

        # Australian
        if "au" in locale:
            return "en", "com.au"

        return "en", "com"

    async def synthesize(
        self,
        text: str,
        profile: VoiceProfile,
        speed: float = 1.0,
        stability: float = 0.5,
        audio_format: str = "mp3",
    ) -> Tuple[bytes, float, str]:
        """Synthesize text into natural human tone MP3 audio using non-blocking executor."""
        lang, tld = self._resolve_lang_and_tld(text, profile)

        def _generate() -> bytes:
            tts = gTTS(text=text, lang=lang, tld=tld, slow=(speed < 0.85))
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            return fp.getvalue()

        # Run synthesis in background thread to avoid blocking async event loop
        loop = asyncio.get_running_loop()
        audio_bytes = await loop.run_in_executor(None, _generate)

        words = len(text.split()) if text else 1
        duration = max(0.5, round(words / (2.6 * speed), 2))
        return audio_bytes, duration, "audio/mpeg"

    async def stream(
        self,
        text: str,
        profile: VoiceProfile,
        speed: float = 1.0,
        stability: float = 0.5,
        audio_format: str = "mp3",
    ) -> AsyncIterator[bytes]:
        """Stream chunks of synthesized MP3 audio."""
        audio_bytes, _, _ = await self.synthesize(text, profile, speed, stability, audio_format)
        chunk_size = 4096
        for i in range(0, len(audio_bytes), chunk_size):
            yield audio_bytes[i : i + chunk_size]
            await asyncio.sleep(0.01)
