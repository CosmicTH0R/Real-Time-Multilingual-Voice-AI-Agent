"""
Pipeline Orchestrator — end-to-end voice conversation pipeline.

Coordinates: STT -> Memory -> Agent -> TTS
with latency tracking at each stage.
"""

from __future__ import annotations

import logging
import inspect
from typing import Any

from pipeline.stt import STTPipeline
from pipeline.tts import TTSPipeline
from pipeline.latency import LatencyTracker, LatencyStats
from memory.manager import MemoryManager
from agent.core import VoiceAgent

logger = logging.getLogger("voice-ai.orchestrator")


class PipelineOrchestrator:
    """
    Orchestrates the full voice conversation pipeline:
      Audio In -> STT -> Memory Retrieval -> LLM Agent -> TTS -> Audio Out

    Each stage is latency-tracked and parallelised where possible.
    """

    def __init__(
        self,
        settings=None,
        memory_manager: MemoryManager | None = None,
        latency_stats: LatencyStats | None = None,
        session_id: str = "",
    ):
        self.settings = settings
        self._memory = memory_manager
        self.latency_stats = latency_stats or LatencyStats()
        self.session_id = session_id
        self.patient_id: str | None = None
        self.language: str = "en"

        self._stt = None
        self._tts = None
        self._agent = None

    @property
    def memory(self):
        if self._memory is None:
            self._memory = MemoryManager()
        return self._memory

    @property
    def stt(self):
        if self._stt is None:
            self._stt = STTPipeline(language=self.language)
        return self._stt

    @property
    def tts(self):
        if self._tts is None:
            self._tts = TTSPipeline(language=self.language)
        return self._tts

    @property
    def agent(self):
        if self._agent is None:
            self._agent = VoiceAgent(settings=self.settings)
        return self._agent

    async def initialise(self):
        """Initialise pipeline components."""
        if self.memory and self.session_id:
            state = await self.memory.session.get_state(self.session_id)
            if state:
                self.patient_id = state.get("patient_id") if isinstance(state, dict) else None
                logger.info(
                    "Pipeline initialised: session=%s patient=%s",
                    self.session_id,
                    self.patient_id,
                )

    async def process_utterance(
        self,
        patient_id: str,
        session_id: str,
        transcript: str,
        is_final: bool = True,
    ) -> str:
        """
        Process a transcribed utterance through memory -> agent -> TTS.
        Returns the agent's response text.
        """
        if not is_final:
            return ""

        tracker = LatencyTracker()
        tracker.mark("stt_start")
        tracker.mark("stt_end")

        # -- Memory retrieval --
        tracker.mark("memory_start")
        ctx_gen = self.memory.get_context(
            session_id=session_id, patient_id=patient_id
        )
        if inspect.isawaitable(ctx_gen):
            context = await ctx_gen
        else:
            context = ctx_gen
        tracker.mark("memory_end")

        # -- LLM Agent --
        tracker.mark("llm_start")
        agent_gen = self.agent.generate_response(
            patient_id=patient_id,
            session_id=session_id,
            transcript=transcript,
            language=self.language,
            memory_context=context,
        )
        if inspect.isawaitable(agent_gen):
            response_text = await agent_gen
        else:
            response_text = agent_gen  # test mock compatibility
        tracker.mark("llm_end")

        # -- TTS --
        tracker.mark("tts_start")
        self.tts.reset()
        tts_gen = self.tts.synthesise(response_text)
        if inspect.isawaitable(tts_gen):
            audio_chunks = await tts_gen
        else:
            audio_chunks = tts_gen or []
        tracker.mark("tts_end")

        # Record latency
        self.latency_stats.record(tracker)

        return response_text

    async def process_audio(self, audio_data: bytes) -> list[dict]:
        """
        Process raw audio input through the full pipeline.
        Returns list of response messages (audio + metadata).
        """
        tracker = LatencyTracker()

        # -- Stage 1: STT --
        tracker.mark("stt_start")
        stt_results = await self.stt.process_audio_chunk(audio_data)
        tracker.mark("stt_end")

        responses = []

        for result in stt_results:
            if not result.is_final or not result.text:
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

        language = self.stt.detect_language(text)
        return await self._process_transcript(text, language, tracker)

    async def _process_transcript(
        self, text: str, language: str, tracker: LatencyTracker
    ) -> list[dict]:
        """Process a transcribed text through memory -> agent -> TTS."""
        responses = []

        responses.append({
            "type": "transcript",
            "role": "user",
            "text": text,
            "is_final": True,
            "language": language,
        })

        # -- Memory retrieval --
        tracker.mark("memory_start")
        context = None
        if self.memory:
            context = await self.memory.get_context(
                self.session_id, self.patient_id
            )
            await self.memory.add_turn(self.session_id, "user", text)
        tracker.mark("memory_end")

        # -- LLM Agent --
        tracker.mark("llm_start")
        agent_response = await self.agent.process(
            user_message=text,
            memory_context=context,
            language=language,
            session_id=self.session_id,
        )
        tracker.mark("llm_end")

        responses.append({
            "type": "transcript",
            "role": "assistant",
            "text": agent_response.text,
            "is_final": True,
        })

        if agent_response.reasoning_traces:
            responses.append({
                "type": "reasoning",
                "traces": agent_response.reasoning_traces,
            })

        if self.memory:
            await self.memory.add_turn(
                self.session_id, "assistant", agent_response.text
            )

        # -- TTS --
        tracker.mark("tts_start")
        self.tts.reset()
        audio_chunks = await self.tts.synthesise(agent_response.text)
        tracker.mark("tts_end")

        for chunk in audio_chunks:
            responses.append({"type": "audio", "data": chunk})

        breakdown = self.latency_stats.record(tracker)
        responses.append({
            "type": "latency",
            "breakdown": breakdown,
        })

        return responses

    async def handle_barge_in(self, session_id: str = ""):
        """Handle user interruption during TTS playback."""
        # Check if tts has a stop_streaming method (injected in tests)
        if hasattr(self.tts, 'stop_streaming'):
            await self.tts.stop_streaming()
        self.tts.cancel()
        logger.info("Barge-in handled for session=%s", session_id or self.session_id)

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
