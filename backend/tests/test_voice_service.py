"""Unit and domain tests for JARVIS Voice Service and Providers."""

import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services.voice.mock_provider import MockVoiceProvider
from app.services.voice.schemas import (
    DEFAULT_VOICE_PROFILES,
    SynthesizeVoiceRequest,
    VoicePreferencesUpdate,
)
from app.services.voice.service import VoiceService


@pytest.fixture
def voice_service() -> VoiceService:
    return VoiceService()


async def create_test_user(db: AsyncSession, email: str = "voice_unit@jarvis.ai") -> User:
    """Helper to persist a user for foreign key constraints."""
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password="testpasswordhash",
        timezone="Asia/Kolkata",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_mock_voice_provider_synthesis():
    """Verify mock provider produces valid WAV and MP3 audio structures."""
    provider = MockVoiceProvider()
    profile = DEFAULT_VOICE_PROFILES["indian_english_male"]

    # Test WAV generation
    wav_bytes, duration_wav, content_wav = await provider.synthesize(
        text="Good morning, sir. All systems are operational.",
        profile=profile,
        audio_format="wav",
    )
    assert content_wav == "audio/wav"
    assert len(wav_bytes) > 44
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"
    assert duration_wav > 0.5

    # Test MP3 generation
    mp3_bytes, duration_mp3, content_mp3 = await provider.synthesize(
        text="Fasting routine is active.",
        profile=profile,
        audio_format="mp3",
    )
    assert content_mp3 == "audio/mpeg"
    assert len(mp3_bytes) > 0
    assert mp3_bytes[:2] == b"\xff\xfb"


@pytest.mark.asyncio
async def test_mock_voice_provider_streaming():
    """Verify mock provider yields incremental audio chunks."""
    provider = MockVoiceProvider()
    profile = DEFAULT_VOICE_PROFILES["neutral_english_female"]

    chunks = []
    async for chunk in provider.stream(
        text="Streaming audio response test.",
        profile=profile,
        audio_format="mp3",
    ):
        chunks.append(chunk)

    assert len(chunks) >= 1
    total_streamed = b"".join(chunks)
    assert len(total_streamed) > 0


def test_standard_voice_profiles_catalog(voice_service: VoiceService):
    """Verify standard PRD 10.2 voice catalog profiles are registered."""
    profiles = voice_service.get_profiles()
    profile_ids = {p.profile_id for p in profiles}

    assert "indian_english_male" in profile_ids
    assert "indian_english_female" in profile_ids
    assert "neutral_english_male" in profile_ids
    assert "neutral_english_female" in profile_ids
    assert "hindi_male" in profile_ids
    assert "hindi_female" in profile_ids
    assert "telugu_male" in profile_ids
    assert "telugu_female" in profile_ids


@pytest.mark.asyncio
async def test_user_preferences_initialization_and_update(
    db_session: AsyncSession,
    voice_service: VoiceService,
):
    """Verify preference initialization, updates, and profile attachment."""
    user = await create_test_user(db_session, "user_pref_test@jarvis.ai")

    # 1. First fetch creates default preferences
    pref = await voice_service.get_user_preferences(db_session, user.id)
    assert pref.user_id == user.id
    assert pref.selected_profile_id == "indian_english_male"
    assert pref.speed == 1.0
    assert pref.voice_enabled is True
    assert pref.privacy_mode is False
    assert pref.active_profile is not None
    assert pref.active_profile.locale == "en-IN"

    # 2. Update preferences
    update_payload = VoicePreferencesUpdate(
        selected_profile_id="hindi_female",
        speed=1.2,
        privacy_mode=True,
    )
    updated = await voice_service.update_user_preferences(
        db=db_session,
        user_id=user.id,
        payload=update_payload,
    )
    assert updated.selected_profile_id == "hindi_female"
    assert updated.speed == 1.2
    assert updated.privacy_mode is True
    assert updated.active_profile.language == "hi"

    # 3. Invalid profile ID rejection
    with pytest.raises(ValueError, match="Unknown voice profile"):
        await voice_service.update_user_preferences(
            db=db_session,
            user_id=user.id,
            payload=VoicePreferencesUpdate(selected_profile_id="nonexistent_profile"),
        )


@pytest.mark.asyncio
async def test_voice_synthesis_and_audit_logging(
    db_session: AsyncSession,
    voice_service: VoiceService,
):
    """Verify synthesis produces base64 audio and updates usage table."""
    user = await create_test_user(db_session, "user_synth_test@jarvis.ai")
    req = SynthesizeVoiceRequest(
        text="Checking server status. Everything is running within normal parameters.",
        format="wav",
    )
    result = await voice_service.synthesize(
        db=db_session,
        user_id=user.id,
        request=req,
    )

    assert result.character_count == len(req.text)
    assert result.duration_seconds > 0.5
    assert result.content_type == "audio/wav"
    assert result.provider == "mock"
    assert len(result.audio_base64) > 0

    # Verify usage metrics
    metrics = await VoiceService.get_user_usage_metrics(db_session, user.id)
    assert metrics.total_requests == 1
    assert metrics.total_characters == len(req.text)
    assert metrics.total_duration_seconds > 0.0


@pytest.mark.asyncio
async def test_voice_disabled_rejects_synthesis(
    db_session: AsyncSession,
    voice_service: VoiceService,
):
    """Verify synthesis is rejected when voice is disabled in preferences."""
    user = await create_test_user(db_session, "user_disabled_test@jarvis.ai")
    await voice_service.update_user_preferences(
        db=db_session,
        user_id=user.id,
        payload=VoicePreferencesUpdate(voice_enabled=False),
    )

    req = SynthesizeVoiceRequest(text="This should fail.")
    with pytest.raises(ValueError, match="Voice synthesis is currently disabled"):
        await voice_service.synthesize(
            db=db_session,
            user_id=user.id,
            request=req,
        )


@pytest.mark.asyncio
async def test_cross_user_voice_usage_isolation(
    db_session: AsyncSession,
    voice_service: VoiceService,
):
    """Verify user usage metrics remain isolated across different users."""
    user_a = await create_test_user(db_session, "user_a_iso@jarvis.ai")
    user_b = await create_test_user(db_session, "user_b_iso@jarvis.ai")

    # User A performs 2 syntheses
    req = SynthesizeVoiceRequest(text="Hello from user A")
    await voice_service.synthesize(db_session, user_a.id, req)
    await voice_service.synthesize(db_session, user_a.id, req)

    metrics_a = await VoiceService.get_user_usage_metrics(db_session, user_a.id)
    metrics_b = await VoiceService.get_user_usage_metrics(db_session, user_b.id)

    assert metrics_a.total_requests == 2
    assert metrics_a.total_characters == len(req.text) * 2
    assert metrics_b.total_requests == 0
    assert metrics_b.total_characters == 0
