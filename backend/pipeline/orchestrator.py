"""
Pipeline Orchestrator — end-to-end voice conversation pipeline.

Coordinates: STT → Memory → Agent → TTS
with latency tracking at each stage.
"""

from __future__ import annotations

import logging
from typing import Any

from config import Settings
from pipeline.stt import STTPipeline
from pipeline.tts import TTSPipeline
from pipeline.latency import LatencyTracker, LatencyStats
from memory.manager import MemoryManager
from agent.core import AgentCore

logger = logging.getLogger("voice-ai.orchestrator")


class PipelineOrchestrator:
    """
    Orchestrates the full voice conversation pipeline:
      Audio In → STT → Memory Retrieval → LLM Agent → TTS → Audio Out

    Each stage is latency-tracked and parallelised where possible.
    """

    def __init__(
        self,
        settings: Settings,
        memory_manager: MemoryManager | None,
        latency_stats: LatencyStats,
        session_id: str,
    ):
        self.settings = settings
        self.memory = memory_manager
        self.latency_stats = latency_stats
        self.session_id = session_id
        self.patient_id: str | None = None
        self.language: str = "en"

        self.stt = STTPipeline(language=self.language)
        self.tts = TTSPipeline(language=self.language)
        self.agent = AgentCore(settings=settings)

    async def initialise(self):
        """Initialise pipeline components."""
        if self.memory:
            state = await self.memory.session.get_state(self.session_id)
            if state:
                self.patient_id = state.get("patient_id")
                logger.info(
                    "Pipeline initialised: session=%s patient=%s",
                    self.session_id,
                    self.patient_id,
                )

    async def process_audio(self, audio_data: bytes) -> list[dict]:
        """
        Process raw audio input through the full pipeline.
        Returns list of response messages (audio + metadata).
        """
        tracker = LatencyTracker()

        # ── Stage 1: STT ──
        tracker.mark("stt_start")
        stt_results = await self.stt.process_audio_chunk(audio_data)
        tracker.mark("stt_end")

        responses = []

        for result in stt_results:
            if not result.is_final or not result.text:
                # Send interim transcript to client
                if result.text:
                    responses.append({
                        "type": "transcript",
                        "role": "user",
                        "text": result.text,
                        "is_final": result.is_final,
                    })
                continue

            # Final transcript — process through agent
            agent_responses = await self._process_transcript(
                result.text, result.language, tracker
            )
            responses.extend(agent_responses)

        return responses

    async def process_text(self, text: str) -> list[dict]:
        """
        Process text input (for testing or text fallback).
        Bypasses STT, goes directly to agent.
        """
        tracker = LatencyTracker()
        tracker.mark("stt_start")
        tracker.mark("stt_end")

        # Detect language from text
        language = self.stt.detect_language(text)

        return await self._process_transcript(text, language, tracker)

    async def _process_transcript(
        self, text: str, language: str, tracker: LatencyTracker
    ) -> list[dict]:
        """Process a transcribed text through memory → agent → TTS."""
        responses = []

        # Send final transcript
        responses.append({
            "type": "transcript",
            "role": "user",
            "text": text,
            "is_final": True,
            "language": language,
        })

        # ── Stage 2: Memory retrieval ──
        tracker.mark("memory_start")
        context = None
        if self.memory:
            context = await self.memory.get_context(
                self.session_id, self.patient_id
            )
            await self.memory.add_turn(self.session_id, "user", text)
        tracker.mark("memory_end")

        # ── Stage 3: LLM Agent ──
        tracker.mark("llm_start")
        agent_response = await self.agent.process(
            user_message=text,
            memory_context=context,
            language=language,
            session_id=self.session_id,
        )
        tracker.mark("llm_end")

        # Send agent text response
        responses.append({
            "type": "transcript",
            "role": "assistant",
            "text": agent_response.text,
            "is_final": True,
        })

        # Send reasoning traces
        if agent_response.reasoning_traces:
            responses.append({
                "type": "reasoning",
                "traces": agent_response.reasoning_traces,
            })

        # Store assistant turn
        if self.memory:
            await self.memory.add_turn(
                self.session_id, "assistant", agent_response.text
            )

        # ── Stage 4: TTS ──
        tracker.mark("tts_start")
        self.tts.reset()
        audio_chunks = await self.tts.synthesise(agent_response.text)
        tracker.mark("tts_end")

        # Stream audio chunks
        for chunk in audio_chunks:
            responses.append({"type": "audio", "data": chunk})

        # ── Record latency ──
        breakdown = self.latency_stats.record(tracker)
        responses.append({
            "type": "latency",
            "breakdown": breakdown,
        })

        return responses

    async def handle_barge_in(self):
        """Handle user interruption during TTS playback."""
        self.tts.cancel()
        logger.info("Barge-in handled for session=%s", self.session_id)

    async def set_language(self, language: str):
        """Update conversation language."""
        self.language = language
        self.stt.set_language(language)
        self.tts.set_language(language)
        logger.info("Language set to %s for session=%s", language, self.session_id)

    async def cleanup(self):
        """Cleanup on WebSocket disconnect."""
        if self.memory:
            await self.memory.save_conversation(
                self.session_id, self.patient_id
            )
        logger.info("Pipeline cleanup done for session=%s", self.session_id)
