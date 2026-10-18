"""Deterministic offline mock voice provider for local development and tests."""

import asyncio
import struct
from typing import AsyncIterator, Tuple
from app.services.voice.base import BaseVoiceProvider
from app.services.voice.schemas import VoiceProfile


class MockVoiceProvider(BaseVoiceProvider):
    """Deterministic, zero-dependency offline speech synthesis provider."""

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def is_configured(self) -> bool:
        return True

    def _generate_mock_wav(self, duration_seconds: float) -> bytes:
        """Create a valid 16-bit 8000Hz mono WAV byte stream."""
        sample_rate = 8000
        num_samples = int(sample_rate * duration_seconds)
        num_channels = 1
        bits_per_sample = 16
        byte_rate = sample_rate * num_channels * (bits_per_sample // 8)
        block_align = num_channels * (bits_per_sample // 8)
        data_size = num_samples * block_align
        riff_size = 36 + data_size

        # Build standard 44-byte WAV header
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            riff_size,
            b"WAVE",
            b"fmt ",
            16,             # Subchunk1Size (16 for PCM)
            1,              # AudioFormat (1 for PCM)
            num_channels,   # Mono
            sample_rate,
            byte_rate,
            block_align,
            bits_per_sample,
            b"data",
            data_size,
        )

        # Deterministic sample pattern (gentle sawtooth tone)
        samples = bytearray(data_size)
        for i in range(num_samples):
            val = (i % 256) - 128
            struct.pack_into("<h", samples, i * 2, val * 100)

        return bytes(header) + bytes(samples)

    def _generate_mock_mp3(self, duration_seconds: float) -> bytes:
        """Create deterministic mock MP3 audio bytes with valid frame sync markers."""
        # Standard MPEG-1 Audio Layer III frame sync header: 0xFF 0xFB
        frame_header = b"\xff\xfb\x90\x00"
        num_frames = max(4, int(duration_seconds * 25))
        payload_frame = frame_header + (b"\xaa\x55" * 150)
        return payload_frame * num_frames

    async def synthesize(
        self,
        text: str,
        profile: VoiceProfile,
        speed: float = 1.0,
        stability: float = 0.5,
        audio_format: str = "mp3",
    ) -> Tuple[bytes, float, str]:
        """Synthesize text into complete audio bytes deterministically."""
        words = len(text.split()) if text else 1
        base_rate = 2.5 * max(0.5, speed)
        duration = max(0.4, round(words / base_rate, 2))

        if audio_format.lower() == "wav":
            content_type = "audio/wav"
            audio_bytes = self._generate_mock_wav(duration)
        else:
            content_type = "audio/mpeg"
            audio_bytes = self._generate_mock_mp3(duration)

        return audio_bytes, duration, content_type

    async def stream(
        self,
        text: str,
        profile: VoiceProfile,
        speed: float = 1.0,
        stability: float = 0.5,
        audio_format: str = "mp3",
    ) -> AsyncIterator[bytes]:
        """Stream synthesized mock audio chunks asynchronously."""
        audio_bytes, _, _ = await self.synthesize(text, profile, speed, stability, audio_format)
        chunk_size = 512
        for i in range(0, len(audio_bytes), chunk_size):
            await asyncio.sleep(0.001)
            yield audio_bytes[i : i + chunk_size]
