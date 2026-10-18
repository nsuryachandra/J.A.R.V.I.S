"""JARVIS Voice system components and services."""

from app.services.voice.base import BaseVoiceProvider
from app.services.voice.elevenlabs_provider import ElevenLabsProvider
from app.services.voice.mock_provider import MockVoiceProvider
from app.services.voice.schemas import (
    DEFAULT_VOICE_PROFILES,
    SynthesizeVoiceRequest,
    VoicePreferencesResponse,
    VoicePreferencesUpdate,
    VoiceProfile,
    VoiceSynthesisResult,
    VoiceUsageMetrics,
)
from app.services.voice.service import VoiceService

__all__ = [
    "BaseVoiceProvider",
    "MockVoiceProvider",
    "ElevenLabsProvider",
    "VoiceProfile",
    "VoicePreferencesResponse",
    "VoicePreferencesUpdate",
    "SynthesizeVoiceRequest",
    "VoiceSynthesisResult",
    "VoiceUsageMetrics",
    "DEFAULT_VOICE_PROFILES",
    "VoiceService",
]
