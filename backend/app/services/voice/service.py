"""Voice orchestration service managing profiles, user preferences, synthesis, and usage metrics."""

import base64
import time
import uuid
from typing import AsyncIterator, Dict, List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.models.voice import VoicePreference, VoiceUsageRecord
from app.services.audit_service import AuditService
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


class VoiceService:
    """Core domain service for JARVIS voice synthesis, preferences, and usage metrics."""

    def __init__(
        self,
        mock_provider: Optional[BaseVoiceProvider] = None,
        live_provider: Optional[BaseVoiceProvider] = None,
    ):
        self._mock = mock_provider or MockVoiceProvider()
        self._elevenlabs = live_provider or ElevenLabsProvider()
        self._profiles: Dict[str, VoiceProfile] = dict(DEFAULT_VOICE_PROFILES)

    def get_profiles(self) -> List[VoiceProfile]:
        """Return all available voice profiles."""
        return list(self._profiles.values())

    def get_profile(self, profile_id: str) -> VoiceProfile:
        """Resolve a profile by ID, falling back to default Indian English Male."""
        return self._profiles.get(profile_id, self._profiles["indian_english_male"])

    def get_active_provider(self) -> BaseVoiceProvider:
        """Determine whether to use live ElevenLabs provider or offline mock provider."""
        settings = get_settings()
        if settings.is_testing or settings.use_mock_voice or not self._elevenlabs.is_configured:
            return self._mock
        return self._elevenlabs

    async def get_user_preferences(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> VoicePreferencesResponse:
        """Retrieve user's voice preferences or initialize default preferences."""
        stmt = select(VoicePreference).where(VoicePreference.user_id == user_id)
        result = await db.execute(stmt)
        pref = result.scalar_one_or_none()

        if not pref:
            pref = VoicePreference(
                user_id=user_id,
                selected_profile_id="indian_english_male",
                speed=1.0,
                stability=0.55,
                similarity_boost=0.8,
                style=0.0,
                voice_enabled=True,
                privacy_mode=False,
            )
            db.add(pref)
            await db.commit()
            await db.refresh(pref)

        active_prof = self.get_profile(pref.selected_profile_id)
        return VoicePreferencesResponse(
            user_id=pref.user_id,
            selected_profile_id=pref.selected_profile_id,
            speed=pref.speed,
            stability=pref.stability,
            similarity_boost=pref.similarity_boost,
            style=pref.style,
            voice_enabled=pref.voice_enabled,
            privacy_mode=pref.privacy_mode,
            active_profile=active_prof,
        )

    async def update_user_preferences(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        payload: VoicePreferencesUpdate,
        session_id: Optional[uuid.UUID] = None,
    ) -> VoicePreferencesResponse:
        """Update user's voice configuration settings and log to audit ledger."""
        stmt = select(VoicePreference).where(VoicePreference.user_id == user_id)
        result = await db.execute(stmt)
        pref = result.scalar_one_or_none()

        if not pref:
            pref = VoicePreference(user_id=user_id)
            db.add(pref)

        if payload.selected_profile_id is not None:
            if payload.selected_profile_id not in self._profiles:
                raise ValueError(f"Unknown voice profile: {payload.selected_profile_id}")
            pref.selected_profile_id = payload.selected_profile_id

        if payload.speed is not None:
            pref.speed = payload.speed
        if payload.stability is not None:
            pref.stability = payload.stability
        if payload.similarity_boost is not None:
            pref.similarity_boost = payload.similarity_boost
        if payload.style is not None:
            pref.style = payload.style
        if payload.voice_enabled is not None:
            pref.voice_enabled = payload.voice_enabled
        if payload.privacy_mode is not None:
            pref.privacy_mode = payload.privacy_mode

        await db.commit()
        await db.refresh(pref)

        # Audit configuration change
        await AuditService.record_event(
            session=db,
            user_id=user_id,
            session_id=session_id,
            action_type="voice.update_preferences",
            resource_scope=f"voice:{pref.selected_profile_id}",
            decision="ALLOW",
            result_status="SUCCESS",
            details={
                "selected_profile_id": pref.selected_profile_id,
                "speed": pref.speed,
                "voice_enabled": pref.voice_enabled,
                "privacy_mode": pref.privacy_mode,
            },
        )
        await db.commit()

        active_prof = self.get_profile(pref.selected_profile_id)
        return VoicePreferencesResponse(
            user_id=pref.user_id,
            selected_profile_id=pref.selected_profile_id,
            speed=pref.speed,
            stability=pref.stability,
            similarity_boost=pref.similarity_boost,
            style=pref.style,
            voice_enabled=pref.voice_enabled,
            privacy_mode=pref.privacy_mode,
            active_profile=active_prof,
        )

    async def synthesize(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        request: SynthesizeVoiceRequest,
        session_id: Optional[uuid.UUID] = None,
    ) -> VoiceSynthesisResult:
        """Synthesize text into complete base64 audio and log usage metrics."""
        pref = await self.get_user_preferences(db, user_id)
        if not pref.voice_enabled:
            raise ValueError("Voice synthesis is currently disabled in your voice preferences.")

        profile_id = request.profile_id or pref.selected_profile_id
        profile = self.get_profile(profile_id)
        speed = request.speed or pref.speed
        stability = request.stability or pref.stability

        provider = self.get_active_provider()
        start_time = time.perf_counter()

        audio_bytes, duration, content_type = await provider.synthesize(
            text=request.text,
            profile=profile,
            speed=speed,
            stability=stability,
            audio_format=request.format,
        )
        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        # Record usage in database
        usage_rec = VoiceUsageRecord(
            user_id=user_id,
            session_id=session_id,
            profile_id=profile.profile_id,
            provider=provider.provider_name,
            character_count=len(request.text),
            duration_seconds=duration,
            latency_ms=latency_ms,
            status="SUCCESS",
        )
        db.add(usage_rec)
        await db.commit()

        # Emit audit entry
        log_details = {
            "provider": provider.provider_name,
            "profile_id": profile.profile_id,
            "character_count": len(request.text),
            "duration_seconds": duration,
            "latency_ms": latency_ms,
        }
        if not pref.privacy_mode:
            log_details["text_preview"] = request.text[:50]

        await AuditService.record_event(
            session=db,
            user_id=user_id,
            session_id=session_id,
            action_type="voice.synthesize",
            resource_scope=f"voice:{profile.profile_id}",
            decision="ALLOW",
            result_status="SUCCESS",
            details=log_details,
        )
        await db.commit()

        return VoiceSynthesisResult(
            audio_base64=base64.b64encode(audio_bytes).decode("ascii"),
            content_type=content_type,
            character_count=len(request.text),
            duration_seconds=duration,
            profile_id=profile.profile_id,
            provider=provider.provider_name,
            latency_ms=latency_ms,
        )

    async def stream_audio(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        request: SynthesizeVoiceRequest,
        session_id: Optional[uuid.UUID] = None,
    ) -> Tuple[AsyncIterator[bytes], str]:
        """Stream synthesized audio chunks and log usage metrics upon completion."""
        pref = await self.get_user_preferences(db, user_id)
        if not pref.voice_enabled:
            raise ValueError("Voice synthesis is currently disabled in your voice preferences.")

        profile_id = request.profile_id or pref.selected_profile_id
        profile = self.get_profile(profile_id)
        speed = request.speed or pref.speed
        stability = request.stability or pref.stability

        provider = self.get_active_provider()
        content_type = "audio/wav" if request.format.lower() == "wav" else "audio/mpeg"

        # Record usage record
        words = len(request.text.split()) if request.text else 1
        est_duration = max(0.4, round(words / (2.5 * speed), 2))
        usage_rec = VoiceUsageRecord(
            user_id=user_id,
            session_id=session_id,
            profile_id=profile.profile_id,
            provider=provider.provider_name,
            character_count=len(request.text),
            duration_seconds=est_duration,
            latency_ms=5.0,
            status="SUCCESS",
        )
        db.add(usage_rec)
        await db.commit()

        stream_gen = provider.stream(
            text=request.text,
            profile=profile,
            speed=speed,
            stability=stability,
            audio_format=request.format,
        )
        return stream_gen, content_type

    @staticmethod
    async def get_user_usage_metrics(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> VoiceUsageMetrics:
        """Calculate aggregated voice character consumption and duration for user."""
        stmt = select(
            func.count(VoiceUsageRecord.id).label("total_requests"),
            func.coalesce(func.sum(VoiceUsageRecord.character_count), 0).label("total_chars"),
            func.coalesce(func.sum(VoiceUsageRecord.duration_seconds), 0.0).label("total_dur"),
            func.coalesce(func.avg(VoiceUsageRecord.latency_ms), 0.0).label("avg_latency"),
        ).where(VoiceUsageRecord.user_id == user_id)

        result = await db.execute(stmt)
        row = result.one()
        return VoiceUsageMetrics(
            user_id=user_id,
            total_requests=int(row.total_requests or 0),
            total_characters=int(row.total_chars or 0),
            total_duration_seconds=round(float(row.total_dur or 0.0), 2),
            avg_latency_ms=round(float(row.avg_latency or 0.0), 2),
        )
