"""
Text-to-Speech pipeline using Google Cloud TTS.

Supports:
  - Multilingual voice synthesis (English, Hindi, Tamil)
  - Streaming audio chunk delivery
  - Mock mode for development
"""

from __future__ import annotations

import asyncio
import logging
import struct
import math
from typing import AsyncGenerator

from config import get_settings

logger = logging.getLogger("voice-ai.tts")
settings = get_settings()

# Voice mapping per language
VOICE_MAP = {
    "en": {"name": "en-IN-Wavenet-D", "language_code": "en-IN"},
    "hi": {"name": "hi-IN-Wavenet-A", "language_code": "hi-IN"},
    "ta": {"name": "ta-IN-Wavenet-A", "language_code": "ta-IN"},
}


class TTSPipeline:
    """
    Text-to-Speech pipeline with streaming support.

    Converts agent text response to audio chunks for WebSocket delivery.
    """

    def __init__(self, language: str = "en"):
        self.language = language
        self._cancelled = False

    async def synthesise(self, text: str) -> list[bytes]:
        """
        Convert text to audio.
        Returns list of audio chunks (for streaming delivery).
        """
        if settings.mock_mode:
            return await self._mock_synthesise(text)

        return await self._live_synthesise(text)

    async def _mock_synthesise(self, text: str) -> list[bytes]:
        """Mock TTS: generate a short sine-wave beep to simulate audio."""
        await asyncio.sleep(0.05)  # Simulate 50ms TTS latency

        # Generate a short 16kHz 16-bit PCM tone (200ms duration)
        sample_rate = 16000
        duration = 0.2
        frequency = 440  # A4 note
        num_samples = int(sample_rate * duration)

        audio_data = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            sample = int(16000 * math.sin(2 * math.pi * frequency * t))
            audio_data.extend(struct.pack("<h", max(-32768, min(32767, sample))))

        # Split into chunks for streaming simulation
        chunk_size = 4000  # ~125ms chunks
        chunks = []
        for i in range(0, len(audio_data), chunk_size):
            if self._cancelled:
                break
            chunks.append(bytes(audio_data[i : i + chunk_size]))

        return chunks

    async def _live_synthesise(self, text: str) -> list[bytes]:
        """
        Live Google Cloud TTS synthesis.
        Will be fully implemented in Phase 5.
        """
        try:
            from google.cloud import texttospeech

            logger.warning("Live TTS not yet fully implemented, use mock_mode=true")
            return []

        except ImportError:
            logger.error("Google Cloud TTS SDK not installed")
            return []

    def cancel(self):
        """Cancel ongoing synthesis (for barge-in support)."""
        self._cancelled = True
        logger.info("TTS synthesis cancelled (barge-in)")

    def reset(self):
        """Reset cancel state."""
        self._cancelled = False

    def set_language(self, language: str):
        """Update synthesis language/voice."""
        self.language = language
        logger.info("TTS language set to: %s", language)
