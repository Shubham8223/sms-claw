"""
Security utilities — OTP, allowlist, HMAC webhook verification, rate limiting.

All functions raise domain exceptions (not HTTP exceptions).
Translation to HTTP 4xx happens in api/routers only.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

import redis.asyncio as aioredis

from sms_claw.core.config import get_settings
from sms_claw.core.constants import OTP_DIGITS, RATE_LIMIT_WINDOW_SECONDS
from sms_claw.core.exceptions import (
    InvalidOTPError,
    PhoneNotAllowedError,
    RateLimitExceededError,
)
from sms_claw.core.logging import get_logger

log = get_logger(__name__)
_s = get_settings()


# ── Allowlist ──────────────────────────────────────────────────────────────────


def assert_phone_allowed(phone: str) -> None:
    """Raise PhoneNotAllowedError if phone is not on the allowlist."""
    if not _s.allowed_phone_numbers or phone not in _s.allowed_phone_numbers:
        log.warning("phone_blocked", phone=phone)
        raise PhoneNotAllowedError()


# ── OTP ────────────────────────────────────────────────────────────────────────


def _otp_key(phone: str) -> str:
    return f"otp:{phone}"


def _enrolled_key(phone: str) -> str:
    return f"enrolled:{phone}"


async def create_otp(phone: str, redis: aioredis.Redis) -> str:
    """Generate a 6-digit OTP, store in Redis with TTL, return the code."""
    code = str(secrets.randbelow(10**OTP_DIGITS)).zfill(OTP_DIGITS)
    await redis.setex(_otp_key(phone), _s.otp_expiry_seconds, code)
    log.info("otp_created", phone=phone)
    return code


async def verify_and_consume_otp(phone: str, code: str, redis: aioredis.Redis) -> None:
    """Verify OTP and mark phone as enrolled. Raises InvalidOTPError on failure."""
    stored: str | None = await redis.get(_otp_key(phone))
    if not stored or not hmac.compare_digest(stored, code.strip()):
        log.warning("otp_invalid", phone=phone)
        raise InvalidOTPError()
    await redis.delete(_otp_key(phone))
    await redis.set(_enrolled_key(phone), "1")
    log.info("otp_verified_enrolled", phone=phone)


async def is_enrolled(phone: str, redis: aioredis.Redis) -> bool:
    return bool(await redis.get(_enrolled_key(phone)))


async def revoke_enrollment(phone: str, redis: aioredis.Redis) -> None:
    await redis.delete(_enrolled_key(phone))
    log.info("enrollment_revoked", phone=phone)


# ── Rate limiting ──────────────────────────────────────────────────────────────


async def assert_rate_limit(phone: str, redis: aioredis.Redis) -> None:
    """Raise RateLimitExceededError if hourly message quota is exceeded."""
    from datetime import datetime, timezone

    window = datetime.now(timezone.utc).strftime("%Y%m%d%H")
    key = f"rl:{phone}:{window}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, RATE_LIMIT_WINDOW_SECONDS)
    if count > _s.rate_limit_messages_per_hour:
        log.warning("rate_limit_exceeded", phone=phone, count=count)
        raise RateLimitExceededError()


# ── HMAC verification ──────────────────────────────────────────────────────────


def verify_twilio_signature(url: str, params: dict, signature: str) -> bool:
    from twilio.request_validator import RequestValidator  # type: ignore[import-untyped]

    return RequestValidator(_s.twilio_auth_token).validate(url, params, signature)


def verify_at_signature(payload_bytes: bytes, signature: str) -> bool:
    expected = hmac.new(
        _s.at_api_key.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
