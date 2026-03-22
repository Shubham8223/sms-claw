"""Session repository — all database operations for Session model."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession as AsyncDBSession

from sms_claw.core.logging import get_logger
from sms_claw.database.models import Session

log = get_logger(__name__)


class SessionRepository:
    def __init__(self, db: AsyncDBSession) -> None:
        self._db = db

    async def create(self, user_id: uuid.UUID) -> Session:
        session = Session(user_id=user_id)
        self._db.add(session)
        await self._db.flush()
        log.info("session_created", session_id=str(session.id), user_id=str(user_id))
        return session

    async def get_by_id(self, session_id: uuid.UUID) -> Session | None:
        result = await self._db.execute(select(Session).where(Session.id == session_id))
        return result.scalar_one_or_none()

    async def close(self, session: Session, summary: str | None = None) -> Session:
        session.ended_at = datetime.now(timezone.utc)
        if summary:
            session.summary = summary
        await self._db.flush()
        log.info("session_closed", session_id=str(session.id))
        return session

    async def increment_message_count(self, session: Session) -> None:
        session.message_count += 1
        await self._db.flush()

    async def list_by_user(self, user_id: uuid.UUID, limit: int = 10) -> list[Session]:
        result = await self._db.execute(
            select(Session)
            .where(Session.user_id == user_id)
            .order_by(Session.started_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent_summaries(
        self, user_id: uuid.UUID, limit: int = 5, since_days: int = 30
    ) -> list[str]:
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
        result = await self._db.execute(
            select(Session.summary)
            .where(
                Session.user_id == user_id,
                Session.ended_at.is_not(None),
                Session.started_at >= cutoff,
                Session.summary.is_not(None),
            )
            .order_by(Session.started_at.desc())
            .limit(limit)
        )
        return [row[0] for row in result.fetchall()]
