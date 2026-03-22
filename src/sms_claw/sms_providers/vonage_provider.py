"""Vonage (Nexmo) SMS adapter."""

from __future__ import annotations

import hashlib
import hmac

import httpx

from sms_claw.core.config import get_settings
from sms_claw.core.logging import get_logger
from sms_claw.sms_providers.base import InboundMessage, OutboundResult, SMSProviderBase

log = get_logger(__name__)

_VONAGE_URL = "https://rest.nexmo.com/sms/json"


class VonageProvider(SMSProviderBase):
    provider_name = "vonage"

    def __init__(self) -> None:
        s = get_settings()
        self._api_key = s.vonage_api_key
        self._api_secret = s.vonage_api_secret
        self._from = s.vonage_from

    async def send(self, to: str, body: str) -> OutboundResult:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    _VONAGE_URL,
                    json={
                        "api_key": self._api_key,
                        "api_secret": self._api_secret,
                        "from": self._from,
                        "to": to.lstrip("+"),
                        "text": body[:160],
                    },
                )
                resp.raise_for_status()
                msg = resp.json()["messages"][0]
                if msg["status"] == "0":
                    log.info("sms_sent", provider="vonage", to=to)
                    return OutboundResult(success=True, message_id=msg["message-id"])
                return OutboundResult(success=False, error=msg.get("error-text"))
        except Exception as exc:
            log.error(
                "sms_send_failed",
                provider="vonage",
                to=to,
                error=str(exc),
                exc_info=True,
            )
            return OutboundResult(success=False, error=str(exc))

    def parse_inbound(self, payload: dict) -> InboundMessage:
        return InboundMessage(
            provider="vonage",
            from_number="+" + payload.get("msisdn", ""),
            to_number="+" + payload.get("to", ""),
            body=payload.get("text", "").strip(),
            message_id=payload.get("messageId", ""),
            raw=payload,
        )

    def verify_webhook(self, request_url: str, payload: dict, headers: dict) -> bool:
        sig = payload.pop("sig", "")
        params = (
            "&".join(f"{k}={v}" for k, v in sorted(payload.items())) + self._api_secret
        )
        expected = hashlib.md5(params.encode()).hexdigest()  # noqa: S324
        return hmac.compare_digest(expected, sig)
