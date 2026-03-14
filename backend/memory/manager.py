"""
Memory Manager — unified interface for session + persistent memory.

Provides context retrieval and prompt injection for the LLM agent.
"""

from __future__ import annotations

import logging
from typing import Any

from config import Settings
from memory.session import SessionMemory
from memory.persistent import PersistentMemory

logger = logging.getLogger("voice-ai.memory")


class MemoryContext:
    """Structured memory context ready for LLM prompt injection."""

    def __init__(
        self,
        session_state: dict | None = None,
        patient_history: dict | None = None,
        language_pref: str = "en",
        conversation_turns: list[dict] | None = None,
    ):
        self.session_state = session_state or {}
        self.patient_history = patient_history or {}
        self.language_pref = language_pref
        self.conversation_turns = conversation_turns or []

    def to_prompt_context(self) -> str:
        """Format memory into a concise string for LLM system prompt."""
        parts = []

        if self.language_pref:
            parts.append(f"Patient language preference: {self.language_pref}")

        if self.patient_history:
            history = self.patient_history
            if history.get("past_appointments"):
                parts.append(
                    f"Past appointments: {len(history['past_appointments'])} total"
                )
                last = history["past_appointments"][-1]
                parts.append(f"Last appointment: {last}")

            if history.get("preferences"):
                parts.append(f"Patient preferences: {history['preferences']}")

        if self.session_state:
            state = self.session_state
            if state.get("current_intent"):
                parts.append(f"Current intent: {state['current_intent']}")
            if state.get("pending_confirmation"):
                parts.append(
                    f"Pending confirmation: {state['pending_confirmation']}"
                )
            if state.get("collected_entities"):
                parts.append(
                    f"Collected info: {state['collected_entities']}"
                )

        return "\n".join(parts) if parts else "No prior context available."


class MemoryManager:
    """
    Unified memory manager combining session (Redis) and
    persistent (PostgreSQL) memory stores.
    """

    def __init__(self, session_memory: SessionMemory, persistent_memory: PersistentMemory):
        self.session = session_memory
        self.persistent = persistent_memory

    @classmethod
    async def create(cls, settings: Settings) -> "MemoryManager":
        """Factory: create and connect memory backends."""
        session_memory = SessionMemory(
            redis_url=settings.redis_url,
            ttl_seconds=settings.session_ttl_seconds,
        )
        await session_memory.connect()

        persistent_memory = PersistentMemory()
        return cls(session_memory, persistent_memory)

    async def create_session(self, session_id: str, patient_id: str | None = None):
        """Initialise a new session in Redis."""
        initial_state = {
            "patient_id": patient_id,
            "current_intent": None,
            "collected_entities": {},
            "pending_confirmation": None,
            "conversation_state": "IDLE",
            "turns": [],
        }
        await self.session.set_state(session_id, initial_state)
        logger.info("Session created in memory: %s", session_id)

    async def get_context(
        self, session_id: str, patient_id: str | None = None
    ) -> MemoryContext:
        """Retrieve merged context from session + persistent memory."""
        session_state = await self.session.get_state(session_id) or {}

        patient_history = {}
        language_pref = "en"

        if patient_id:
            patient_history = await self.persistent.get_patient_history(patient_id)
            language_pref = await self.persistent.get_language_pref(patient_id) or "en"

        turns = session_state.get("turns", [])

        return MemoryContext(
            session_state=session_state,
            patient_history=patient_history,
            language_pref=language_pref,
            conversation_turns=turns,
        )

    async def update_session(self, session_id: str, updates: dict):
        """Update session state in Redis."""
        current = await self.session.get_state(session_id) or {}
        current.update(updates)
        await self.session.set_state(session_id, current)

    async def add_turn(self, session_id: str, role: str, content: str):
        """Add a conversation turn to session memory."""
        state = await self.session.get_state(session_id) or {}
        turns = state.get("turns", [])
        turns.append({"role": role, "content": content})
        state["turns"] = turns
        await self.session.set_state(session_id, state)

    async def save_conversation(self, session_id: str, patient_id: str | None = None):
        """Persist session conversation to PostgreSQL."""
        state = await self.session.get_state(session_id)
        if state and state.get("turns"):
            await self.persistent.save_conversation(
                session_id=session_id,
                patient_id=patient_id,
                turns=state["turns"],
                language=state.get("language", "en"),
            )

    async def close(self):
        """Cleanup connections."""
        await self.session.close()
