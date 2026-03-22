"""
Long-term memory domain service.

Wraps MemoryRepository and UserRepository.
Exposes semantic save/search to the agent and services.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from sms_claw.core.logging import get_logger
from sms_claw.repositories.memory_repo import MemoryRepository
from sms_claw.repositories.user_repo import UserRepository

log = get_logger(__name__)


class LongTermMemory:
    def __init__(self, db: AsyncSession) -> None:
        self._mem_repo = MemoryRepository(db)
        self._user_repo = UserRepository(db)

    async def save(self, phone: str, content: str, category: str = "general") -> None:
        user = await self._user_repo.get_by_phone(phone)
        if not user:
            log.warning("ltm_save_no_user", phone=phone)
            return
        await self._mem_repo.create(user_id=user.id, content=content, category=category)

    async def search(self, phone: str, query: str, limit: int = 5) -> list[str]:
        user = await self._user_repo.get_by_phone(phone)
        if not user:
            return []
        return await self._mem_repo.search(user_id=user.id, query=query, limit=limit)

    async def get_preferences(self, phone: str) -> dict:
        user = await self._user_repo.get_by_phone(phone)
        return user.preferences if user else {}
