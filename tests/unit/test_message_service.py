"""Unit tests — MessageService orchestration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sms_claw.core.exceptions import PhoneNotAllowedError
from sms_claw.services.message_service import MessageService


@pytest.mark.asyncio
async def test_handle_blocked_phone_returns_none(mock_db, mock_redis):
    with patch(
        "sms_claw.services.message_service.EnrollmentService.handle_inbound",
        side_effect=PhoneNotAllowedError(),
    ):
        svc = MessageService(mock_db, mock_redis)
        result = await svc.handle("+910000000000", "hi")
    assert result is None


@pytest.mark.asyncio
async def test_handle_enrollment_flow_returns_otp_message(mock_db, mock_redis):
    with patch(
        "sms_claw.services.message_service.EnrollmentService.handle_inbound",
        return_value="Your OTP is 123456",
    ):
        svc = MessageService(mock_db, mock_redis)
        result = await svc.handle("+919876543210", "hi")
    assert result == "Your OTP is 123456"


@pytest.mark.asyncio
async def test_handle_rate_limited_returns_message(mock_db, mock_redis):
    from sms_claw.core.exceptions import RateLimitExceededError

    with patch(
        "sms_claw.services.message_service.EnrollmentService.handle_inbound",
        return_value=None,
    ):
        with patch(
            "sms_claw.services.message_service.assert_rate_limit",
            side_effect=RateLimitExceededError(),
        ):
            svc = MessageService(mock_db, mock_redis)
            result = await svc.handle("+919876543210", "hi")
    assert result is not None
    assert (
        "limit" in result.lower()
        or "slow" in result.lower()
        or "too many" in result.lower()
    )


@pytest.mark.asyncio
async def test_handle_enrolled_runs_agent(mock_db, mock_redis):
    fake_session = MagicMock()
    fake_session.id = "00000000-0000-0000-0000-000000000001"

    with patch(
        "sms_claw.services.message_service.EnrollmentService.handle_inbound",
        return_value=None,
    ):
        with patch("sms_claw.services.message_service.assert_rate_limit"):
            with patch(
                "sms_claw.services.message_service.SessionService.start",
                return_value=fake_session,
            ):
                with patch(
                    "sms_claw.services.message_service.run_agent",
                    return_value="42",
                ):
                    svc = MessageService(mock_db, mock_redis)
                    result = await svc.handle("+919876543210", "What is 6*7?")
    assert result == "42"


@pytest.mark.asyncio
async def test_handle_agent_exception_returns_error_message(mock_db, mock_redis):
    fake_session = MagicMock()
    fake_session.id = "00000000-0000-0000-0000-000000000002"

    with patch(
        "sms_claw.services.message_service.EnrollmentService.handle_inbound",
        return_value=None,
    ):
        with patch("sms_claw.services.message_service.assert_rate_limit"):
            with patch(
                "sms_claw.services.message_service.SessionService.start",
                return_value=fake_session,
            ):
                with patch(
                    "sms_claw.services.message_service.run_agent",
                    side_effect=RuntimeError("boom"),
                ):
                    svc = MessageService(mock_db, mock_redis)
                    result = await svc.handle("+919876543210", "crash me")
    assert result is not None
    assert len(result) > 0
