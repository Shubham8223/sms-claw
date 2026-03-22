"""Twilio SMS adapter."""

from __future__ import annotations

import asyncio

from sms_claw.core.config import get_settings
from sms_claw.core.logging import get_logger
from sms_claw.sms_providers.base import InboundMessage, OutboundResult, SMSProviderBase

log = get_logger(__name__)


class TwilioProvider(SMSProviderBase):
    provider_name = "twilio"

    def __init__(self) -> None:
        from twilio.request_validator import RequestValidator  # type: ignore[import-untyped]
        from twilio.rest import Client  # type: ignore[import-untyped]

        s = get_settings()
        self._client = Client(s.twilio_account_sid, s.twilio_auth_token)
        self._from = s.twilio_phone_number
        self._validator = RequestValidator(s.twilio_auth_token)

    async def send(self, to: str, body: str) -> OutboundResult:
        try:
            loop = asyncio.get_event_loop()
            msg = await loop.run_in_executor(
                None,
                lambda: self._client.messages.create(
                    to=to, from_=self._from, body=body[:1600]
                ),
            )
            log.info("sms_sent", provider="twilio", to=to, sid=msg.sid)
            return OutboundResult(success=True, message_id=msg.sid)
        except Exception as exc:
            log.error(
                "sms_send_failed",
                provider="twilio",
                to=to,
                error=str(exc),
                exc_info=True,
            )
            return OutboundResult(success=False, error=str(exc))

    def parse_inbound(self, payload: dict) -> InboundMessage:
        return InboundMessage(
            provider="twilio",
            from_number=payload.get("From", ""),
            to_number=payload.get("To", ""),
            body=payload.get("Body", "").strip(),
            message_id=payload.get("MessageSid", ""),
            raw=payload,
        )

    def verify_webhook(self, request_url: str, payload: dict, headers: dict) -> bool:
        sig = headers.get("X-Twilio-Signature", "")
        return self._validator.validate(request_url, payload, sig)
