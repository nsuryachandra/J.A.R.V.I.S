"""Abstract base interface for speech synthesis providers."""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Tuple
from app.services.voice.schemas import VoiceProfile


class BaseVoiceProvider(ABC):
    """Abstract interface defining required voice provider capabilities."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the voice provider implementation."""
        pass

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """True if provider has credentials and is ready for live requests."""
        pass

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        profile: VoiceProfile,
        speed: float = 1.0,
        stability: float = 0.5,
        audio_format: str = "mp3",
    ) -> Tuple[bytes, float, str]:
        """Synthesize text into complete audio bytes.
        
        Returns:
            Tuple of (audio_bytes, estimated_duration_seconds, content_type)
        """
        pass

    @abstractmethod
    async def stream(
        self,
        text: str,
        profile: VoiceProfile,
        speed: float = 1.0,
        stability: float = 0.5,
        audio_format: str = "mp3",
    ) -> AsyncIterator[bytes]:
        """Stream synthesized audio chunks asynchronously."""
        pass
