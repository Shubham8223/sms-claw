"""Unit tests — SMS provider adapters."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sms_claw.sms_providers.base import InboundMessage, OutboundResult


def test_twilio_parse_inbound():
    with patch("sms_claw.sms_providers.twilio_provider.get_settings") as ms:
        ms.return_value.twilio_account_sid = "ACtest"
        ms.return_value.twilio_auth_token = "token"
        ms.return_value.twilio_phone_number = "+10000000000"
        with patch("sms_claw.sms_providers.twilio_provider.Client"):
            with patch("sms_claw.sms_providers.twilio_provider.RequestValidator"):
                from sms_claw.sms_providers.twilio_provider import TwilioProvider

                p = TwilioProvider()
                msg = p.parse_inbound(
                    {
                        "From": "+919876543210",
                        "To": "+10000000000",
                        "Body": "Hello world",
                        "MessageSid": "SM123",
                    }
                )
    assert msg.from_number == "+919876543210"
    assert msg.body == "Hello world"
    assert msg.provider == "twilio"
    assert msg.message_id == "SM123"


def test_at_parse_inbound():
    with patch("sms_claw.sms_providers.africas_talking_provider.get_settings") as ms:
        ms.return_value.at_api_key = "key"
        ms.return_value.at_username = "sandbox"
        ms.return_value.at_sender_id = "TEST"
        from sms_claw.sms_providers.africas_talking_provider import (
            AfricasTalkingProvider,
        )

        p = AfricasTalkingProvider()
        msg = p.parse_inbound(
            {"from": "+919876543210", "to": "TEST", "text": "Hi", "id": "AT1"}
        )
    assert msg.from_number == "+919876543210"
    assert msg.body == "Hi"
    assert msg.provider == "africas_talking"


def test_vonage_parse_inbound():
    with patch("sms_claw.sms_providers.vonage_provider.get_settings") as ms:
        ms.return_value.vonage_api_key = "key"
        ms.return_value.vonage_api_secret = "secret"
        ms.return_value.vonage_from = "DISPATCH"
        from sms_claw.sms_providers.vonage_provider import VonageProvider

        p = VonageProvider()
        msg = p.parse_inbound(
            {
                "msisdn": "919876543210",
                "to": "DISPATCH",
                "text": "Test",
                "messageId": "V1",
            }
        )
    assert msg.from_number == "+919876543210"
    assert msg.body == "Test"
    assert msg.provider == "vonage"


@pytest.mark.asyncio
async def test_mock_provider_send(mock_provider):
    result = await mock_provider.send("+919876543210", "Test message")
    assert result.success is True
    assert result.message_id == "mock-001"
    assert mock_provider.sent[0]["body"] == "Test message"


def test_mock_provider_verify_webhook(mock_provider):
    assert mock_provider.verify_webhook("http://test", {}, {}) is True


def test_registry_raises_for_unknown_provider():
    from sms_claw.sms_providers.registry import _REGISTRY, get_sms_provider
    from functools import lru_cache

    get_sms_provider.cache_clear()
    with patch("sms_claw.sms_providers.registry.get_settings") as ms:
        ms.return_value.default_sms_provider = "nonexistent"
        with pytest.raises(ValueError, match="not registered"):
            get_sms_provider()
    get_sms_provider.cache_clear()
