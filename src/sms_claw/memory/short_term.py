"""
Short-term memory domain service.

Wraps SessionRepository + MessageRepository with domain-level operations.
Never touches the DB directly — all queries go through repositories.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from sms_claw.core.logging import get_logger
from sms_claw.database.models import Session
from sms_claw.repositories.message_repo import MessageRepository
from sms_claw.repositories.session_repo import SessionRepository
from sms_claw.repositories.user_repo import UserRepository

log = get_logger(__name__)


class ShortTermMemory:
    def __init__(self, db: AsyncSession) -> None:
        self._user_repo = UserRepository(db)
        self._session_repo = SessionRepository(db)
        self._msg_repo = MessageRepository(db)

    async def start_session(self, phone: str) -> Session:
        user, created = await self._user_repo.get_or_create(phone)
        if created:
            log.info("new_user_first_session", phone=phone)
        return await self._session_repo.create(user_id=user.id)

    async def log_message(
        self,
        session_id: uuid.UUID,
        role: str,
        content: str,
        tool_calls: dict | None = None,
    ) -> None:
        await self._msg_repo.create(
            session_id=session_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
        )
        session = await self._session_repo.get_by_id(session_id)
        if session:
            await self._session_repo.increment_message_count(session)

    async def close_session(
        self, session_id: uuid.UUID, summary: str | None = None
    ) -> None:
        session = await self._session_repo.get_by_id(session_id)
        if session:
            await self._session_repo.close(session, summary=summary)

    async def get_recent_summaries(self, phone: str, limit: int = 5) -> list[str]:
        user = await self._user_repo.get_by_phone(phone)
        if not user:
            return []
        return await self._session_repo.get_recent_summaries(user.id, limit=limit)
