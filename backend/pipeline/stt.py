"""
Speech-to-Text pipeline using Deepgram streaming.

Supports:
  - Streaming partial + final transcription
  - Language detection (en, hi, ta)
  - VAD (Voice Activity Detection) for barge-in
  - Mock mode for development without API costs
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import AsyncGenerator

from config import get_settings

logger = logging.getLogger("voice-ai.stt")
settings = get_settings()

# Language code mapping
LANGUAGE_MAP = {
    "en": "en-IN",
    "hi": "hi",
    "ta": "ta",
}


class STTResult:
    """Result from speech-to-text processing."""

    def __init__(
        self,
        text: str,
        is_final: bool = False,
        language: str = "en",
        confidence: float = 1.0,
        duration_ms: float = 0,
    ):
        self.text = text
        self.is_final = is_final
        self.language = language
        self.confidence = confidence
        self.duration_ms = duration_ms


class STTPipeline:
    """
    Speech-to-Text pipeline with streaming support.

    In mock mode, simulates realistic STT with configurable delay.
    In live mode, connects to Deepgram's streaming API.
    """

    def __init__(self, language: str = "en"):
        self.language = language
        self._buffer: bytearray = bytearray()
        self._is_speaking = False
        self._silence_start: float | None = None
        self._silence_threshold_ms = 500  # VAD: ms of silence to detect end

    async def process_audio_chunk(self, audio_data: bytes) -> list[STTResult]:
        """
        Process incoming audio chunk.
        Returns list of STT results (partial or final).
        """
        if settings.mock_mode:
            return await self._mock_process(audio_data)

        return await self._live_process(audio_data)

    async def _mock_process(self, audio_data: bytes) -> list[STTResult]:
        """Mock STT: buffer audio and return simulated transcriptions."""
        self._buffer.extend(audio_data)

        # Simulate: every ~32KB of audio (~1 second at 16kHz 16-bit)
        # produces a mock transcript
        if len(self._buffer) >= 32000:
            self._buffer.clear()
            await asyncio.sleep(0.05)  # Simulate 50ms STT latency
            return [
                STTResult(
                    text="",  # Will be filled by text_input fallback
                    is_final=True,
                    language=self.language,
                    confidence=0.95,
                    duration_ms=50,
                )
            ]

        return []

    async def _live_process(self, audio_data: bytes) -> list[STTResult]:
        """
        Live Deepgram streaming STT.

        Uses Deepgram's WebSocket API for real-time transcription
        with language detection.
        """
        try:
            from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions

            # This will be fully implemented in Phase 3
            # For now, return empty to prevent errors
            logger.warning("Live STT not yet fully implemented, use mock_mode=true")
            return []

        except ImportError:
            logger.error("Deepgram SDK not installed")
            return []

    def detect_language(self, text: str) -> str:
        """
        Simple language detection heuristic.
        Falls back to the set language if detection is uncertain.
        """
        if not text:
            return self.language

        # Basic heuristic: check Unicode script ranges
        tamil_count = sum(1 for c in text if "\u0B80" <= c <= "\u0BFF")
        hindi_count = sum(1 for c in text if "\u0900" <= c <= "\u097F")
        latin_count = sum(1 for c in text if c.isascii() and c.isalpha())

        total = tamil_count + hindi_count + latin_count
        if total == 0:
            return self.language

        if tamil_count / total > 0.3:
            return "ta"
        if hindi_count / total > 0.3:
            return "hi"
        return "en"

    def set_language(self, language: str):
        """Update the target language for STT."""
        self.language = language
        logger.info("STT language set to: %s", language)
