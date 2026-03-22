"""Integration tests — webhook HTTP endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_generic_webhook_blocked_phone_returns_ok_no_reply(
    client, mock_db, mock_redis, mock_provider
):
    """Blocked phone: 200 OK but no SMS sent (silent drop)."""
    with patch("sms_claw.api.routers.webhook.get_db", return_value=mock_db):
        with patch("sms_claw.api.routers.webhook.get_redis", return_value=mock_redis):
            with patch(
                "sms_claw.api.routers.webhook.get_provider", return_value=mock_provider
            ):
                with patch(
                    "sms_claw.api.routers.webhook.MessageService.handle",
                    return_value=None,
                ):
                    resp = await client.post(
                        "/webhook/generic",
                        json={"from": "+910000000000", "body": "hello"},
                    )
    assert resp.status_code == 200
    assert len(mock_provider.sent) == 0


@pytest.mark.asyncio
async def test_generic_webhook_otp_flow(client, mock_db, mock_redis, mock_provider):
    """First contact — OTP sent back."""
    with patch("sms_claw.api.routers.webhook.get_db", return_value=mock_db):
        with patch("sms_claw.api.routers.webhook.get_redis", return_value=mock_redis):
            with patch(
                "sms_claw.api.routers.webhook.get_provider", return_value=mock_provider
            ):
                with patch(
                    "sms_claw.api.routers.webhook.MessageService.handle",
                    return_value="Your OTP is 123456. Expires in 5 min.",
                ):
                    resp = await client.post(
                        "/webhook/generic",
                        json={"from": "+919876543210", "body": "hello"},
                    )
    assert resp.status_code == 200
    assert len(mock_provider.sent) == 1
    assert "123456" in mock_provider.sent[0]["body"]


@pytest.mark.asyncio
async def test_generic_webhook_agent_reply(client, mock_db, mock_redis, mock_provider):
    """Enrolled user — agent reply sent back."""
    with patch("sms_claw.api.routers.webhook.get_db", return_value=mock_db):
        with patch("sms_claw.api.routers.webhook.get_redis", return_value=mock_redis):
            with patch(
                "sms_claw.api.routers.webhook.get_provider", return_value=mock_provider
            ):
                with patch(
                    "sms_claw.api.routers.webhook.MessageService.handle",
                    return_value="The capital of France is Paris.",
                ):
                    resp = await client.post(
                        "/webhook/generic",
                        json={"from": "+919876543210", "body": "Capital of France?"},
                    )
    assert resp.status_code == 200
    assert len(mock_provider.sent) == 1
    assert "Paris" in mock_provider.sent[0]["body"]


@pytest.mark.asyncio
async def test_generic_webhook_disabled_in_production(client):
    """Generic endpoint must return 404 in production."""
    with patch("sms_claw.api.routers.webhook._s") as ms:
        ms.is_production = True
        resp = await client.post(
            "/webhook/generic",
            json={"from": "+919876543210", "body": "hello"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_health_returns_status(client, mock_db, mock_redis):
    with patch("sms_claw.api.routers.admin.get_db", return_value=mock_db):
        with patch("sms_claw.api.routers.admin.get_redis", return_value=mock_redis):
            mock_db.execute = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)
            with patch(
                "sms_claw.api.routers.admin.AdminService.health",
                new_callable=AsyncMock,
            ) as mock_health:
                from sms_claw.services.admin_service import HealthStatus

                mock_health.return_value = HealthStatus(
                    status="healthy",
                    database="ok",
                    redis="ok",
                    sms_provider="twilio",
                    llm_provider="anthropic",
                    environment="development",
                )
                resp = await client.get("/admin/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["database"] == "ok"


@pytest.mark.asyncio
async def test_admin_channels_returns_config(client, mock_db, mock_redis):
    with patch("sms_claw.api.routers.admin.get_db", return_value=mock_db):
        with patch("sms_claw.api.routers.admin.get_redis", return_value=mock_redis):
            with patch(
                "sms_claw.api.routers.admin.AdminService.channel_status",
                new_callable=AsyncMock,
            ) as mock_ch:
                from sms_claw.services.admin_service import ChannelStatus

                mock_ch.return_value = ChannelStatus(
                    sms={
                        "provider": "twilio",
                        "twilio": True,
                        "africas_talking": False,
                        "vonage": False,
                    },
                    llm={
                        "provider": "anthropic",
                        "anthropic": True,
                        "openai": False,
                        "google": False,
                    },
                    tools={
                        "web_search": True,
                        "web_browse": True,
                        "whatsapp": False,
                        "email": False,
                        "github": False,
                        "telegram": False,
                    },
                )
                resp = await client.get("/admin/channels")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sms"]["provider"] == "twilio"
    assert data["llm"]["provider"] == "anthropic"
