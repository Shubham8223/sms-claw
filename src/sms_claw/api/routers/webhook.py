"""
Webhook router — HTTP only.

Each handler:
  1. Verifies the provider signature (raises 403 on failure in production).
  2. Parses the inbound message via the provider adapter.
  3. Calls MessageService.handle → gets reply string or None.
  4. Sends the reply via the provider adapter.
  5. Returns 200.

No business logic lives here.
"""

from __future__ import annotations

from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from sms_claw.api.dependencies import get_db, get_provider, get_redis
from sms_claw.core.config import get_settings
from sms_claw.core.logging import get_logger
from sms_claw.services.message_service import MessageService
from sms_claw.sms_providers.base import SMSProviderBase

log = get_logger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])
_s = get_settings()


async def _send_reply(provider: SMSProviderBase, to: str, body: str) -> None:
    result = await provider.send(to=to, body=body)
    if not result.success:
        log.error("reply_send_failed", to=to, error=result.error)


# ── Twilio ─────────────────────────────────────────────────────────────────────


@router.post("/twilio")
async def twilio_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
    provider: Annotated[SMSProviderBase, Depends(get_provider)],
    From: str = Form(...),
    Body: str = Form(...),
) -> dict:
    payload = dict(await request.form())

    if _s.is_production:
        sig = request.headers.get("X-Twilio-Signature", "")
        if not provider.verify_webhook(
            str(request.url), payload, {"X-Twilio-Signature": sig}
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature"
            )

    msg = provider.parse_inbound(payload)
    reply = await MessageService(db, redis).handle(msg.from_number, msg.body)
    if reply:
        await _send_reply(provider, msg.from_number, reply)
    return {"status": "ok"}


# ── Africa's Talking ───────────────────────────────────────────────────────────


@router.post("/africas-talking")
async def at_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
    provider: Annotated[SMSProviderBase, Depends(get_provider)],
) -> dict:
    payload = dict(await request.form())

    if _s.is_production:
        sig = request.headers.get("X-AfricasTalking-Signature", "")
        if not provider.verify_webhook(
            "", payload, {"X-AfricasTalking-Signature": sig}
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature"
            )

    msg = provider.parse_inbound(payload)
    reply = await MessageService(db, redis).handle(msg.from_number, msg.body)
    if reply:
        await _send_reply(provider, msg.from_number, reply)
    return {"status": "ok"}


# ── Vonage ─────────────────────────────────────────────────────────────────────


@router.post("/vonage")
async def vonage_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
    provider: Annotated[SMSProviderBase, Depends(get_provider)],
) -> dict:
    payload = await request.json()

    if _s.is_production:
        if not provider.verify_webhook("", payload, dict(request.headers)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature"
            )

    msg = provider.parse_inbound(payload)
    reply = await MessageService(db, redis).handle(msg.from_number, msg.body)
    if reply:
        await _send_reply(provider, msg.from_number, reply)
    return {"status": "ok"}


# ── Generic (dev/testing only) ─────────────────────────────────────────────────


@router.post("/generic")
async def generic_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
    provider: Annotated[SMSProviderBase, Depends(get_provider)],
) -> dict:
    """Dev-only endpoint. Disabled in production. JSON: {"from": "+91...", "body": "..."}"""
    if _s.is_production:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    data = await request.json()
    phone = data.get("from", "")
    body = data.get("body", "")

    log.info("generic_webhook", phone=phone, body=body[:40])
    reply = await MessageService(db, redis).handle(phone, body)
    if reply:
        await _send_reply(provider, phone, reply)
    return {"status": "ok", "reply": reply}
