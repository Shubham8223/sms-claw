"""
Admin service — read-only queries for the admin API.

Returns plain dicts / dataclasses so routers can serialise them freely.
No HTTP imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from sms_claw.core.config import get_settings
from sms_claw.core.logging import get_logger
from sms_claw.repositories.memory_repo import MemoryRepository
from sms_claw.repositories.session_repo import SessionRepository
from sms_claw.repositories.user_repo import UserRepository
from sms_claw.security.auth import revoke_enrollment

log = get_logger(__name__)
_s = get_settings()


@dataclass
class HealthStatus:
    status: str
    database: str
    redis: str
    sms_provider: str
    llm_provider: str
    environment: str


@dataclass
class UserSummary:
    id: str
    phone: str
    enrolled_at: datetime
    preferences: dict = field(default_factory=dict)


@dataclass
class SessionSummary:
    id: str
    started_at: datetime
    ended_at: datetime | None
    message_count: int
    summary: str | None


@dataclass
class MemorySummary:
    phone: str
    preferences: dict
    memories: list[dict]


@dataclass
class ChannelStatus:
    sms: dict
    llm: dict
    tools: dict


class AdminService:
    def __init__(self, db: AsyncSession, redis: aioredis.Redis) -> None:
        self._db = db
        self._redis = redis
        self._user_repo = UserRepository(db)
        self._session_repo = SessionRepository(db)
        self._mem_repo = MemoryRepository(db)

    async def health(self) -> HealthStatus:
        db_ok = "ok"
        redis_ok = "ok"
        try:
            await self._db.execute(text("SELECT 1"))
        except Exception as exc:
            db_ok = f"error: {exc}"
            log.error("health_db_error", error=str(exc), exc_info=True)
        try:
            await self._redis.ping()
        except Exception as exc:
            redis_ok = f"error: {exc}"
            log.error("health_redis_error", error=str(exc), exc_info=True)

        overall = "healthy" if db_ok == "ok" and redis_ok == "ok" else "degraded"
        return HealthStatus(
            status=overall,
            database=db_ok,
            redis=redis_ok,
            sms_provider=_s.default_sms_provider,
            llm_provider=_s.default_llm_provider,
            environment=_s.app_env,
        )

    async def list_users(self) -> list[UserSummary]:
        users = await self._user_repo.list_all(limit=50)
        return [
            UserSummary(
                id=str(u.id),
                phone=u.phone,
                enrolled_at=u.enrolled_at,
                preferences=u.preferences,
            )
            for u in users
        ]

    async def get_user_memory(self, phone: str) -> MemorySummary | None:
        user = await self._user_repo.get_by_phone(phone)
        if not user:
            return None
        memories = await self._mem_repo.list_by_user(user.id, limit=20)
        return MemorySummary(
            phone=phone,
            preferences=user.preferences,
            memories=[
                {
                    "content": m.content,
                    "category": m.category,
                    "created_at": m.created_at.isoformat(),
                }
                for m in memories
            ],
        )

    async def get_user_sessions(self, phone: str) -> list[SessionSummary]:
        user = await self._user_repo.get_by_phone(phone)
        if not user:
            return []
        sessions = await self._session_repo.list_by_user(user.id, limit=10)
        return [
            SessionSummary(
                id=str(s.id),
                started_at=s.started_at,
                ended_at=s.ended_at,
                message_count=s.message_count,
                summary=s.summary,
            )
            for s in sessions
        ]

    async def channel_status(self) -> ChannelStatus:
        s = _s
        return ChannelStatus(
            sms={
                "provider": s.default_sms_provider,
                "twilio": bool(s.twilio_account_sid),
                "africas_talking": bool(s.at_api_key),
                "vonage": bool(s.vonage_api_key),
            },
            llm={
                "provider": s.default_llm_provider,
                "anthropic": bool(s.anthropic_api_key),
                "openai": bool(s.openai_api_key),
                "google": bool(s.google_api_key),
            },
            tools={
                "web_search": bool(s.tavily_api_key or s.serpapi_api_key),
                "web_browse": True,
                "whatsapp": bool(s.whatsapp_api_token),
                "email": bool(s.smtp_username),
                "github": bool(s.github_token),
                "telegram": bool(s.telegram_bot_token),
            },
        )

    async def revoke_user_enrollment(self, phone: str) -> None:
        await revoke_enrollment(phone, self._redis)
        log.info("enrollment_revoked_by_admin", phone=phone)
