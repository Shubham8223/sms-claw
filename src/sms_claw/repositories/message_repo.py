"""Message log repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sms_claw.database.models import MessageLog


class MessageRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        session_id: uuid.UUID,
        role: str,
        content: str,
        tool_calls: dict | None = None,
    ) -> MessageLog:
        msg = MessageLog(
            session_id=session_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
        )
        self._db.add(msg)
        await self._db.flush()
        return msg

    async def list_by_session(self, session_id: uuid.UUID) -> list[MessageLog]:
        result = await self._db.execute(
            select(MessageLog)
            .where(MessageLog.session_id == session_id)
            .order_by(MessageLog.created_at.asc())
        )
        return list(result.scalars().all())
