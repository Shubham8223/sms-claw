"""
Session service — start, close, and query sessions.

Wraps repositories; never touches HTTP.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from sms_claw.core.logging import get_logger
from sms_claw.database.models import Session
from sms_claw.repositories.session_repo import SessionRepository
from sms_claw.repositories.user_repo import UserRepository

log = get_logger(__name__)


class SessionService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._user_repo = UserRepository(db)
        self._session_repo = SessionRepository(db)

    async def start(self, phone: str) -> Session:
        """Get or create the user then open a new session."""
        user, _ = await self._user_repo.get_or_create(phone)
        return await self._session_repo.create(user_id=user.id)

    async def close(self, session_id: uuid.UUID, summary: str | None = None) -> None:
        session = await self._session_repo.get_by_id(session_id)
        if session:
            await self._session_repo.close(session, summary=summary)

    async def get_recent_sessions(self, phone: str, limit: int = 10) -> list[Session]:
        user = await self._user_repo.get_by_phone(phone)
        if not user:
            return []
        return await self._session_repo.list_by_user(user.id, limit=limit)
