"""Unit tests — security/auth.py"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from sms_claw.core.exceptions import (
    InvalidOTPError,
    PhoneNotAllowedError,
    RateLimitExceededError,
)
from sms_claw.security.auth import (
    assert_phone_allowed,
    assert_rate_limit,
    create_otp,
    verify_and_consume_otp,
)


def test_allowed_phone_passes():
    with patch("sms_claw.security.auth._s") as s:
        s.allowed_phone_numbers = ["+919876543210"]
        assert_phone_allowed("+919876543210")  # no exception


def test_blocked_phone_raises():
    with patch("sms_claw.security.auth._s") as s:
        s.allowed_phone_numbers = ["+919876543210"]
        with pytest.raises(PhoneNotAllowedError):
            assert_phone_allowed("+910000000000")


def test_empty_allowlist_blocks_all():
    with patch("sms_claw.security.auth._s") as s:
        s.allowed_phone_numbers = []
        with pytest.raises(PhoneNotAllowedError):
            assert_phone_allowed("+919876543210")


@pytest.mark.asyncio
async def test_create_otp_is_six_digits():
    redis = AsyncMock()
    redis.setex = AsyncMock()
    with patch("sms_claw.security.auth._s") as s:
        s.otp_expiry_seconds = 300
        otp = await create_otp("+919876543210", redis)
    assert len(otp) == 6
    assert otp.isdigit()


@pytest.mark.asyncio
async def test_verify_otp_success():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value="123456")
    redis.delete = AsyncMock()
    redis.set = AsyncMock()
    await verify_and_consume_otp("+919876543210", "123456", redis)
    redis.delete.assert_awaited_once()
    redis.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_verify_otp_wrong_code_raises():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value="123456")
    with pytest.raises(InvalidOTPError):
        await verify_and_consume_otp("+919876543210", "999999", redis)


@pytest.mark.asyncio
async def test_verify_otp_expired_raises():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    with pytest.raises(InvalidOTPError):
        await verify_and_consume_otp("+919876543210", "123456", redis)


@pytest.mark.asyncio
async def test_rate_limit_allows_under_threshold():
    redis = AsyncMock()
    redis.incr = AsyncMock(return_value=5)
    redis.expire = AsyncMock()
    with patch("sms_claw.security.auth._s") as s:
        s.rate_limit_messages_per_hour = 20
        await assert_rate_limit("+919876543210", redis)  # no exception


@pytest.mark.asyncio
async def test_rate_limit_blocks_over_threshold():
    redis = AsyncMock()
    redis.incr = AsyncMock(return_value=21)
    redis.expire = AsyncMock()
    with patch("sms_claw.security.auth._s") as s:
        s.rate_limit_messages_per_hour = 20
        with pytest.raises(RateLimitExceededError):
            await assert_rate_limit("+919876543210", redis)
