"""
Message service — orchestrates one full SMS turn.

Flow
----
1.  EnrollmentService.handle_inbound  → OTP flows or None (enrolled)
2.  Security: rate limit check
3.  SessionService.start             → new Session row
4.  Agent: run_agent                 → reply string
5.  SessionService.log_turn          → persist turn
6.  Return reply string

This layer owns no HTTP logic. Every exception it raises is a domain exception.
"""

from __future__ import annotations

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from sms_claw.agent.graph import run_agent
from sms_claw.agent.prompts import ERROR_MESSAGE, RATE_LIMIT_MESSAGE
from sms_claw.core.exceptions import PhoneNotAllowedError, RateLimitExceededError
from sms_claw.core.logging import get_logger
from sms_claw.security.auth import assert_rate_limit
from sms_claw.services.enrollment_service import EnrollmentService
from sms_claw.services.session_service import SessionService

log = get_logger(__name__)


class MessageService:
    def __init__(self, db: AsyncSession, redis: aioredis.Redis) -> None:
        self._db = db
        self._redis = redis
        self._enrollment = EnrollmentService(db, redis)
        self._session = SessionService(db)

    async def handle(self, phone: str, body: str) -> str | None:
        """
        Process one inbound SMS.

        Returns
        -------
        str   — the reply to send back via SMS.
        None  — phone was silently dropped (not on allowlist).
        """
        bound_log = log.bind(phone=phone)

        # ── 1. Allowlist + enrollment ─────────────────────────────────────────
        try:
            enrollment_reply = await self._enrollment.handle_inbound(phone, body)
        except PhoneNotAllowedError:
            bound_log.warning("phone_silently_dropped")
            return None  # Silent drop — do not reveal gateway exists

        if enrollment_reply is not None:
            return enrollment_reply  # OTP flow reply

        # ── 2. Rate limit ─────────────────────────────────────────────────────
        try:
            await assert_rate_limit(phone, self._redis)
        except RateLimitExceededError:
            bound_log.warning("rate_limit_hit")
            return RATE_LIMIT_MESSAGE

        # ── 3. Session ────────────────────────────────────────────────────────
        session = await self._session.start(phone)
        session_id = str(session.id)
        bound_log = bound_log.bind(session_id=session_id)
        bound_log.info("agent_starting", body_preview=body[:40])

        # ── 4. Agent ──────────────────────────────────────────────────────────
        try:
            reply = await run_agent(
                phone=phone,
                session_id=session_id,
                user_message=body,
                db=self._db,
                redis=self._redis,
            )
        except Exception as exc:
            bound_log.error("agent_unhandled_error", error=str(exc), exc_info=True)
            reply = ERROR_MESSAGE

        bound_log.info("agent_replied", preview=reply[:60])
        return reply
