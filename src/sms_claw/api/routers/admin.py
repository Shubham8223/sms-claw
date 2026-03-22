"""
Admin router — HTTP only, delegates all logic to AdminService.

Endpoints
---------
GET  /admin/health
GET  /admin/users
GET  /admin/users/{phone}/memory
GET  /admin/users/{phone}/sessions
GET  /admin/channels
DELETE /admin/users/{phone}/enroll
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from sms_claw.api.dependencies import get_db, get_redis
from sms_claw.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/health")
async def health(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> dict:
    result = await AdminService(db, redis).health()
    return asdict(result)


@router.get("/users")
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> list[dict]:
    users = await AdminService(db, redis).list_users()
    return [asdict(u) for u in users]


@router.get("/users/{phone}/memory")
async def get_memory(
    phone: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> dict:
    result = await AdminService(db, redis).get_user_memory(phone)
    return asdict(result) if result else {"error": "User not found"}


@router.get("/users/{phone}/sessions")
async def get_sessions(
    phone: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> list[dict]:
    sessions = await AdminService(db, redis).get_user_sessions(phone)
    return [asdict(s) for s in sessions]


@router.get("/channels")
async def channel_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> dict:
    result = await AdminService(db, redis).channel_status()
    return asdict(result)


@router.delete("/users/{phone}/enroll")
async def revoke_enrollment(
    phone: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> dict:
    await AdminService(db, redis).revoke_user_enrollment(phone)
    return {"revoked": phone}
