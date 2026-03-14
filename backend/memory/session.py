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
        self._redis: aioredis.Redis | None = None

    async def connect(self):
        """Connect to Redis."""
        self._redis = aioredis.from_url(
            self.redis_url,
            decode_responses=True,
        )
        logger.info("Session memory connected to Redis")

    def _key(self, session_id: str) -> str:
        return f"voiceai:session:{session_id}"

    async def get_state(self, session_id: str) -> dict | None:
        """Get full session state."""
        if not self._redis:
            return None
        data = await self._redis.get(self._key(session_id))
        if data:
            return json.loads(data)
        return None

    async def set_state(self, session_id: str, state: dict):
        """Set full session state with TTL refresh."""
        if not self._redis:
            return
        await self._redis.setex(
            self._key(session_id),
            self.ttl,
            json.dumps(state, default=str),
        )

    async def delete_session(self, session_id: str):
        """Delete a session."""
        if self._redis:
            await self._redis.delete(self._key(session_id))

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            logger.info("Session memory Redis connection closed")
