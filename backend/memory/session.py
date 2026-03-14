"""
Redis-backed session memory with TTL.

Stores within-session state: intent, entities, conversation turns,
pending confirmations, and conversation state machine.
"""

from __future__ import annotations

import logging
import json
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger("voice-ai.memory.session")


class SessionMemory:
    """Redis-backed session memory with automatic TTL expiration."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0", ttl_seconds: int = 1800):
        self.redis_url = redis_url
        self.ttl = ttl_seconds
        self.redis: aioredis.Redis | None = None

    async def connect(self):
        """Connect to Redis."""
        self.redis = aioredis.from_url(
            self.redis_url,
            decode_responses=False,
        )
        logger.info("Session memory connected to Redis")

    def _key(self, session_id: str, suffix: str = "") -> str:
        key = f"session:{session_id}"
        if suffix:
            key += f":{suffix}"
        return key

    # ── Intent ──

    async def update_intent(self, session_id: str, intent: str):
        """Update the current intent for the session."""
        if not self.redis:
            return
        await self.redis.setex(
            self._key(session_id, "intent"),
            self.ttl,
            intent.encode() if isinstance(intent, str) else intent,
        )

    async def get_intent(self, session_id: str) -> str | None:
        """Get the current intent for the session."""
        if not self.redis:
            return None
        data = await self.redis.get(self._key(session_id, "intent"))
        if data:
            return data.decode() if isinstance(data, bytes) else data
        return None

    # ── Entities ──

    async def add_entity(self, session_id: str, key: str, value: Any):
        """Add an extracted entity to the session."""
        if not self.redis:
            return
        existing = await self.redis.get(self._key(session_id, "entities"))
        entities = json.loads(existing.decode()) if existing else {}
        entities[key] = value
        await self.redis.setex(
            self._key(session_id, "entities"),
            self.ttl,
            json.dumps(entities).encode(),
        )

    async def get_entities(self, session_id: str) -> dict:
        """Get all extracted entities for the session."""
        if not self.redis:
            return {}
        data = await self.redis.get(self._key(session_id, "entities"))
        if data:
            return json.loads(data.decode() if isinstance(data, bytes) else data)
        return {}

    # ── State ──

    async def get_state(self, session_id: str) -> str | None:
        """Get the conversation state machine phase."""
        if not self.redis:
            return None
        data = await self.redis.get(self._key(session_id, "state"))
        if data:
            return data.decode() if isinstance(data, bytes) else data
        return None

    async def set_state(self, session_id: str, state: str | dict):
        """Set the conversation state."""
        if not self.redis:
            return
        if isinstance(state, dict):
            state = json.dumps(state, default=str)
        await self.redis.setex(
            self._key(session_id, "state"),
            self.ttl,
            state.encode() if isinstance(state, str) else state,
        )

    # ── Turns ──

    async def add_turn(self, session_id: str, role: str, content: str):
        """Append a conversation turn."""
        if not self.redis:
            return
        existing = await self.redis.get(self._key(session_id, "turns"))
        turns = json.loads(existing.decode()) if existing else []
        turns.append({"role": role, "content": content})
        await self.redis.setex(
            self._key(session_id, "turns"),
            self.ttl,
            json.dumps(turns).encode(),
        )

    async def get_turns(self, session_id: str) -> list[dict]:
        """Get the conversation turn history."""
        if not self.redis:
            return []
        data = await self.redis.get(self._key(session_id, "turns"))
        if data:
            return json.loads(data.decode() if isinstance(data, bytes) else data)
        return []

    # ── Lifecycle ──

    async def delete_session(self, session_id: str):
        """Delete all keys for a session."""
        if self.redis:
            for suffix in ["intent", "entities", "state", "turns"]:
                await self.redis.delete(self._key(session_id, suffix))

    async def close(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            logger.info("Session memory Redis connection closed")
