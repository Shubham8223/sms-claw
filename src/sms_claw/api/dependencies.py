"""FastAPI dependency providers — db session, Redis, SMS provider."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from sms_claw.core.config import get_settings
from sms_claw.database.base import AsyncSessionLocal
from sms_claw.sms_providers.base import SMSProviderBase
from sms_claw.sms_providers.registry import get_sms_provider

_s = get_settings()


@lru_cache(maxsize=1)
def _redis_pool() -> aioredis.Redis:
    return aioredis.from_url(
        _s.redis_url, encoding="utf-8", decode_responses=True, max_connections=20
    )


async def get_redis() -> aioredis.Redis:
    return _redis_pool()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_provider() -> SMSProviderBase:
    return get_sms_provider()
