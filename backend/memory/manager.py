"""
Memory Manager — unified interface for session + persistent memory.

Provides context retrieval and prompt injection for the LLM agent.
"""

from __future__ import annotations

import logging
from typing import Any

from memory.session import SessionMemory
from memory.persistent import PersistentMemory

logger = logging.getLogger("voice-ai.memory")


class MemoryContext:
    """Structured memory context ready for LLM prompt injection."""

    def __init__(
        self,
        intent: str | None = None,
        entities: dict | None = None,
        state: str | None = None,
        turns: list[dict] | None = None,
        patient_profile: dict | None = None,
        recent_history: list[dict] | None = None,
        language_pref: str = "en",
    ):
        self.intent = intent
        self.entities = entities or {}
        self.state = state
        self.turns = turns or []
        self.patient_profile = patient_profile or {}
        self.recent_history = recent_history or []
        self.language_pref = language_pref

        # Alias for backward compatibility
        self.conversation_turns = self.turns
        self.session_state = {
            "current_intent": self.intent,
            "collected_entities": self.entities,
            "conversation_state": self.state,
        }
        self.patient_history = {
            "name": self.patient_profile.get("name", ""),
            "past_appointments": self.recent_history,
        }

    @property
    def formatted_prompt(self) -> str:
        """Format memory into a concise string for LLM system prompt."""
        return self.to_prompt_context()

    def to_prompt_context(self) -> str:
        """Format memory into a concise string for LLM system prompt."""
        parts = []

        if self.patient_profile:
            name = self.patient_profile.get("name", "")
            if name:
                parts.append(f"Patient name: {name}")
            lang = self.patient_profile.get("language_pref", "")
            if lang:
                parts.append(f"Preferred language: {lang}")

        if self.intent:
            parts.append(f"Current intent: {self.intent}")

        if self.entities:
            parts.append(f"Collected info: {self.entities}")

        if self.recent_history:
            parts.append(f"Recent appointments: {len(self.recent_history)} total")

        if self.state:
            parts.append(f"Conversation state: {self.state}")

        return "\n".join(parts) if parts else "No prior context available."


class MemoryManager:
    """
    Unified memory manager combining session (Redis) and
    persistent (PostgreSQL) memory stores.
    """

    def __init__(self, session_memory: SessionMemory | None = None, persistent_memory: PersistentMemory | None = None):
        self.session = session_memory or SessionMemory()
        self.persistent = persistent_memory or PersistentMemory()

    @classmethod
    async def create(cls, settings=None) -> "MemoryManager":
        """Factory: create and connect memory backends."""
        redis_url = "redis://localhost:6379/0"
        ttl = 1800
        if settings:
            redis_url = settings.redis_url
            ttl = settings.session_ttl_seconds

        session_memory = SessionMemory(redis_url=redis_url, ttl_seconds=ttl)
        await session_memory.connect()

        persistent_memory = PersistentMemory()
        return cls(session_memory, persistent_memory)

    async def get_context(
        self, session_id: str | None = None, patient_id: str | None = None
    ) -> MemoryContext:
        """Retrieve merged context from session + persistent memory."""
        intent = None
        entities = {}
        state = None
        turns = []
        patient_profile = {}
        recent_history = []

        if session_id:
            intent = await self.session.get_intent(session_id)
            entities = await self.session.get_entities(session_id)
            state = await self.session.get_state(session_id)
            turns = await self.session.get_turns(session_id)

        if patient_id:
            patient_profile = await self.persistent.get_patient_profile(patient_id)
            recent_history = await self.persistent.get_recent_history(patient_id)

        return MemoryContext(
            intent=intent,
            entities=entities,
            state=state,
            turns=turns,
            patient_profile=patient_profile,
            recent_history=recent_history,
            language_pref=patient_profile.get("language_pref", "en") if patient_profile else "en",
        )

    async def update_session(self, session_id: str, updates: dict):
        """Update session state in Redis."""
        if "intent" in updates:
            await self.session.update_intent(session_id, updates["intent"])
        if "entities" in updates:
            for k, v in updates["entities"].items():
                await self.session.add_entity(session_id, k, v)
        if "state" in updates:
            await self.session.set_state(session_id, updates["state"])

    async def add_turn(self, session_id: str, role: str, content: str):
        """Add a conversation turn to session memory."""
        await self.session.add_turn(session_id, role, content)

    async def save_conversation(self, session_id: str, patient_id: str | None = None):
        """Persist session conversation to PostgreSQL."""
        if session_id:
            turns = await self.session.get_turns(session_id)
            if turns:
                await self.persistent.save_conversation(
                    session_id=session_id,
                    patient_id=patient_id,
                    turns=turns,
                )

    async def close(self):
        """Cleanup connections."""
        await self.session.close()
