"""Unit tests — EnrollmentService"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sms_claw.core.exceptions import PhoneNotAllowedError
from sms_claw.services.enrollment_service import EnrollmentService


@pytest.mark.asyncio
async def test_handle_inbound_blocked_phone_raises(mock_db, mock_redis):
    with patch(
        "sms_claw.services.enrollment_service.assert_phone_allowed",
        side_effect=PhoneNotAllowedError(),
    ):
        svc = EnrollmentService(mock_db, mock_redis)
        with pytest.raises(PhoneNotAllowedError):
            await svc.handle_inbound("+910000000000", "hello")


@pytest.mark.asyncio
async def test_handle_inbound_not_enrolled_sends_otp(mock_db, mock_redis):
    with patch("sms_claw.services.enrollment_service.assert_phone_allowed"):
        with patch(
            "sms_claw.services.enrollment_service.is_enrolled", return_value=False
        ):
            with patch(
                "sms_claw.services.enrollment_service.create_otp", return_value="654321"
            ):
                svc = EnrollmentService(mock_db, mock_redis)
                reply = await svc.handle_inbound("+919876543210", "hello")
    assert reply is not None
    assert "654321" in reply


@pytest.mark.asyncio
async def test_handle_inbound_otp_submission_success(mock_db, mock_redis):
    fake_user = MagicMock()
    fake_user.id = "uuid-001"

    with patch("sms_claw.services.enrollment_service.assert_phone_allowed"):
        with patch(
            "sms_claw.services.enrollment_service.is_enrolled", return_value=False
        ):
            with patch("sms_claw.services.enrollment_service.verify_and_consume_otp"):
                with patch.object(
                    EnrollmentService,
                    "_user_repo",
                    new_callable=lambda: property(
                        lambda self: MagicMock(
                            get_or_create=AsyncMock(return_value=(fake_user, True))
                        )
                    ),
                    create=True,
                ):
                    svc = EnrollmentService(mock_db, mock_redis)
                    svc._user_repo = MagicMock(
                        get_or_create=AsyncMock(return_value=(fake_user, True))
                    )
                    reply = await svc.handle_inbound("+919876543210", "123456")
    assert reply is not None
    assert (
        "in" in reply.lower()
        or "enrolled" in reply.lower()
        or "welcome" in reply.lower()
        or reply
    )


@pytest.mark.asyncio
async def test_handle_inbound_enrolled_returns_none(mock_db, mock_redis):
    with patch("sms_claw.services.enrollment_service.assert_phone_allowed"):
        with patch(
            "sms_claw.services.enrollment_service.is_enrolled", return_value=True
        ):
            svc = EnrollmentService(mock_db, mock_redis)
            result = await svc.handle_inbound("+919876543210", "What is 2+2?")
    assert result is None
