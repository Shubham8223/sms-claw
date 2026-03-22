"""Working memory — Redis-backed per-session message window."""

from __future__ import annotations

import json

import redis.asyncio as aioredis
from langchain_core.messages import BaseMessage, messages_from_dict, messages_to_dict

from sms_claw.core.constants import (
    WORKING_MEMORY_MAX_MESSAGES,
    WORKING_MEMORY_TTL_SECONDS,
)
from sms_claw.core.logging import get_logger

log = get_logger(__name__)


class WorkingMemory:
    """Stores the live conversation window for the current session in Redis."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._r = redis

    @staticmethod
    def _key(session_id: str) -> str:
        return f"wm:{session_id}"

    async def load(self, session_id: str) -> list[BaseMessage]:
        raw = await self._r.get(self._key(session_id))
        if not raw:
            return []
        try:
            return messages_from_dict(json.loads(raw))
        except Exception as exc:
            log.warning(
                "working_memory_load_error",
                session_id=session_id,
                error=str(exc),
                exc_info=True,
            )
            return []

    async def save(self, session_id: str, messages: list[BaseMessage]) -> None:
        trimmed = messages[-WORKING_MEMORY_MAX_MESSAGES:]
        await self._r.setex(
            self._key(session_id),
            WORKING_MEMORY_TTL_SECONDS,
            json.dumps(messages_to_dict(trimmed)),
        )

    async def clear(self, session_id: str) -> None:
        await self._r.delete(self._key(session_id))
