"""User repository — all database operations for the User model."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sms_claw.core.logging import get_logger
from sms_claw.database.models import User

log = get_logger(__name__)


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_phone(self, phone: str) -> User | None:
        result = await self._db.execute(select(User).where(User.phone == phone))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self._db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create(self, phone: str) -> User:
        user = User(phone=phone)
        self._db.add(user)
        await self._db.flush()
        log.info("user_created", phone=phone, user_id=str(user.id))
        return user

    async def get_or_create(self, phone: str) -> tuple[User, bool]:
        """Return (user, created). created=True if newly inserted."""
        user = await self.get_by_phone(phone)
        if user:
            return user, False
        return await self.create(phone), True

    async def update_preferences(self, user: User, prefs: dict) -> User:
        user.preferences = {**user.preferences, **prefs}
        await self._db.flush()
        log.info("preferences_updated", phone=user.phone)
        return user

    async def list_all(self, limit: int = 50) -> list[User]:
        result = await self._db.execute(
            select(User).order_by(User.enrolled_at.desc()).limit(limit)
        )
        return list(result.scalars().all())
