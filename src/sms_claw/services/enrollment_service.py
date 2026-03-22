"""
Enrollment service — manages the OTP-based phone enrollment flow.

Responsibilities
----------------
- Check allowlist
- Issue OTP
- Verify OTP and mark phone enrolled
- Create user record on successful enrollment

No HTTP, no FastAPI. Raises domain exceptions only.
"""

from __future__ import annotations

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from sms_claw.agent.prompts import (
    ENROLLED_MESSAGE,
    INVALID_OTP_MESSAGE,
    OTP_MESSAGE,
)
from sms_claw.core.config import get_settings
from sms_claw.core.exceptions import InvalidOTPError, PhoneNotAllowedError
from sms_claw.core.logging import get_logger
from sms_claw.repositories.user_repo import UserRepository
from sms_claw.security.auth import (
    assert_phone_allowed,
    create_otp,
    is_enrolled,
    verify_and_consume_otp,
)

log = get_logger(__name__)
_s = get_settings()


class EnrollmentService:
    def __init__(self, db: AsyncSession, redis: aioredis.Redis) -> None:
        self._db = db
        self._redis = redis
        self._user_repo = UserRepository(db)

    async def check_enrolled(self, phone: str) -> bool:
        return await is_enrolled(phone, self._redis)

    async def begin_enrollment(self, phone: str) -> str:
        """
        Assert phone is allowed, generate OTP, return the SMS body to send.
        Raises PhoneNotAllowedError if blocked.
        """
        assert_phone_allowed(phone)
        otp = await create_otp(phone, self._redis)
        log.info("enrollment_started", phone=phone)
        return OTP_MESSAGE.format(otp=otp, expiry_mins=_s.otp_expiry_seconds // 60)

    async def complete_enrollment(self, phone: str, code: str) -> str:
        """
        Verify OTP, create user record, return success/failure SMS body.
        Never raises — returns a human-readable SMS string instead so the
        caller can always reply to the user.
        """
        try:
            await verify_and_consume_otp(phone, code, self._redis)
        except InvalidOTPError:
            return INVALID_OTP_MESSAGE

        user, created = await self._user_repo.get_or_create(phone)
        if created:
            log.info("user_enrolled_first_time", phone=phone)
        else:
            log.info("user_re_enrolled", phone=phone)

        return ENROLLED_MESSAGE

    async def handle_inbound(self, phone: str, body: str) -> str | None:
        """
        Auto-enroll allowed phones — no OTP required.
        Returns None immediately so the agent handles the message.
        Raises PhoneNotAllowedError if phone is not on the allowlist.
        """
        assert_phone_allowed(phone)

        enrolled = await is_enrolled(phone, self._redis)
        if not enrolled:
            await self._user_repo.get_or_create(phone)
            await self._redis.set(f"enrolled:{phone}", "1")
            log.info("auto_enrolled", phone=phone)

        return None  # always let the agent handle the message
