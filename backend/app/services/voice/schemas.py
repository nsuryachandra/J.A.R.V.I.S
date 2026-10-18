"""Voice profile, preference, synthesis, and usage schemas for JARVIS."""

import uuid
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class VoiceProfile(BaseModel):
    """Voice profile definition as specified in PRD 10.2."""

    profile_id: str = Field(description="Unique profile identifier, e.g. indian_english_male")
    display_name: str = Field(description="Human-friendly profile name")
    provider: str = Field(default="elevenlabs", description="TTS provider name")
    voice_id: str = Field(description="Provider-specific voice identifier")
    language: str = Field(description="ISO language code, e.g. en, hi, te")
    locale: str = Field(description="Regional locale, e.g. en-IN, hi-IN, te-IN, en-US")
    gender: str = Field(description="male or female")
    tone: str = Field(default="professional", description="professional, casual, calm")
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    stability: float = Field(default=0.5, ge=0.0, le=1.0)
    similarity_boost: float = Field(default=0.75, ge=0.0, le=1.0)
    style: float = Field(default=0.0, ge=0.0, le=1.0)
    description: str = Field(default="")


class VoicePreferencesResponse(BaseModel):
    """User-facing voice configuration and preferences."""

    user_id: uuid.UUID
    selected_profile_id: str
    speed: float
    stability: float
    similarity_boost: float
    style: float
    voice_enabled: bool
    privacy_mode: bool
    active_profile: Optional[VoiceProfile] = None


class VoicePreferencesUpdate(BaseModel):
    """Payload for updating user voice preferences."""

    selected_profile_id: Optional[str] = Field(default=None)
    speed: Optional[float] = Field(default=None, ge=0.5, le=2.0)
    stability: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    similarity_boost: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    style: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    voice_enabled: Optional[bool] = Field(default=None)
    privacy_mode: Optional[bool] = Field(default=None)


class SynthesizeVoiceRequest(BaseModel):
    """Request payload for text-to-speech generation."""

    text: str = Field(min_length=1, max_length=5000, description="Text to synthesize")
    profile_id: Optional[str] = Field(default=None, description="Optional profile override")
    speed: Optional[float] = Field(default=None, ge=0.5, le=2.0)
    stability: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    format: str = Field(default="mp3", description="Audio format: mp3 or wav")


class VoiceSynthesisResult(BaseModel):
    """Result of speech synthesis including audio and performance metrics."""

    audio_base64: str = Field(description="Base64-encoded audio bytes")
    content_type: str = Field(description="MIME type of the audio e.g. audio/mpeg or audio/wav")
    character_count: int
    duration_seconds: float
    profile_id: str
    provider: str
    latency_ms: float


class VoiceUsageMetrics(BaseModel):
    """Aggregated voice synthesis usage metrics for a user."""

    user_id: uuid.UUID
    total_requests: int
    total_characters: int
    total_duration_seconds: float
    avg_latency_ms: float


# -----------------------------------------------------------------------------
# Default Voice Profiles Catalog (PRD 10.2)
# -----------------------------------------------------------------------------

DEFAULT_VOICE_PROFILES: Dict[str, VoiceProfile] = {
    "indian_english_male": VoiceProfile(
        profile_id="indian_english_male",
        display_name="Aditya — Indian English Male",
        provider="elevenlabs",
        voice_id="XB0fDUnXU5ikFXr333ED",
        language="en",
        locale="en-IN",
        gender="male",
        tone="professional",
        speed=1.0,
        stability=0.55,
        similarity_boost=0.8,
        style=0.0,
        description="Warm, polished, professional Indian English male persona.",
    ),
    "indian_english_female": VoiceProfile(
        profile_id="indian_english_female",
        display_name="Kavita — Indian English Female",
        provider="elevenlabs",
        voice_id="EXAVITQu4vr4xnSDxMaL",
        language="en",
        locale="en-IN",
        gender="female",
        tone="professional",
        speed=1.0,
        stability=0.55,
        similarity_boost=0.8,
        style=0.0,
        description="Clear, articulate, professional Indian English female persona.",
    ),
    "neutral_english_male": VoiceProfile(
        profile_id="neutral_english_male",
        display_name="Adam — Neutral English Male",
        provider="elevenlabs",
        voice_id="pNInz6obpgDQGcFmaJgB",
        language="en",
        locale="en-US",
        gender="male",
        tone="professional",
        speed=1.0,
        stability=0.5,
        similarity_boost=0.75,
        style=0.0,
        description="Balanced, neutral international English male voice.",
    ),
    "neutral_english_female": VoiceProfile(
        profile_id="neutral_english_female",
        display_name="Rachel — Neutral English Female",
        provider="elevenlabs",
        voice_id="21m00Tcm4TlvDq8ikWAM",
        language="en",
        locale="en-US",
        gender="female",
        tone="calm",
        speed=1.0,
        stability=0.5,
        similarity_boost=0.75,
        style=0.0,
        description="Soothing, clear, neutral international English female voice.",
    ),
    "hindi_male": VoiceProfile(
        profile_id="hindi_male",
        display_name="Aarav — Hindi Male",
        provider="elevenlabs",
        voice_id="onwK4e9ZLuTAKqWW03F9",
        language="hi",
        locale="hi-IN",
        gender="male",
        tone="calm",
        speed=1.0,
        stability=0.6,
        similarity_boost=0.75,
        style=0.0,
        description="Natural, expressive Hindi male voice for conversational briefings.",
    ),
    "hindi_female": VoiceProfile(
        profile_id="hindi_female",
        display_name="Ananya — Hindi Female",
        provider="elevenlabs",
        voice_id="ThT5KcBeYPX3keUQqHPh",
        language="hi",
        locale="hi-IN",
        gender="female",
        tone="professional",
        speed=1.0,
        stability=0.6,
        similarity_boost=0.75,
        style=0.0,
        description="Articulate, polite Hindi female voice.",
    ),
    "telugu_male": VoiceProfile(
        profile_id="telugu_male",
        display_name="Karthik — Telugu Male",
        provider="elevenlabs",
        voice_id="TX3LPaxmHKxFdv7VOQHJ",
        language="te",
        locale="te-IN",
        gender="male",
        tone="casual",
        speed=1.0,
        stability=0.6,
        similarity_boost=0.75,
        style=0.0,
        description="Fluent, pleasant Telugu male voice.",
    ),
    "telugu_female": VoiceProfile(
        profile_id="telugu_female",
        display_name="Lakshmi — Telugu Female",
        provider="elevenlabs",
        voice_id="jBpfuIE2acCO8z3wKNLl",
        language="te",
        locale="te-IN",
        gender="female",
        tone="calm",
        speed=1.0,
        stability=0.6,
        similarity_boost=0.75,
        style=0.0,
        description="Gentle, natural Telugu female voice.",
    ),
}
