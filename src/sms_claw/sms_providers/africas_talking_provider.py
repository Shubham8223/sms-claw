"""Africa's Talking SMS adapter."""

from __future__ import annotations

import hashlib
import hmac

import httpx

from sms_claw.core.config import get_settings
from sms_claw.core.logging import get_logger
from sms_claw.sms_providers.base import InboundMessage, OutboundResult, SMSProviderBase

log = get_logger(__name__)

_SEND_URL = "https://api.africastalking.com/version1/messaging"
_SANDBOX_URL = "https://api.sandbox.africastalking.com/version1/messaging"


class AfricasTalkingProvider(SMSProviderBase):
    provider_name = "africas_talking"

    def __init__(self) -> None:
        s = get_settings()
        self._api_key = s.at_api_key
        self._username = s.at_username
        self._sender_id = s.at_sender_id
        self._url = _SANDBOX_URL if s.at_username == "sandbox" else _SEND_URL

    async def send(self, to: str, body: str) -> OutboundResult:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    self._url,
                    headers={"apiKey": self._api_key, "Accept": "application/json"},
                    data={
                        "username": self._username,
                        "to": to,
                        "message": body[:160],
                        "from": self._sender_id,
                    },
                )
                resp.raise_for_status()
                entry = resp.json()["SMSMessageData"]["Recipients"][0]
                if entry["status"] == "Success":
                    log.info("sms_sent", provider="africas_talking", to=to)
                    return OutboundResult(success=True, message_id=entry["messageId"])
                return OutboundResult(success=False, error=entry["status"])
        except Exception as exc:
            log.error(
                "sms_send_failed",
                provider="africas_talking",
                to=to,
                error=str(exc),
                exc_info=True,
            )
            return OutboundResult(success=False, error=str(exc))

    def parse_inbound(self, payload: dict) -> InboundMessage:
        return InboundMessage(
            provider="africas_talking",
            from_number=payload.get("from", ""),
            to_number=payload.get("to", ""),
            body=payload.get("text", "").strip(),
            message_id=payload.get("id", ""),
            raw=payload,
        )

    def verify_webhook(self, request_url: str, payload: dict, headers: dict) -> bool:
        sig = headers.get("X-AfricasTalking-Signature", "")
        body = "&".join(f"{k}={v}" for k, v in sorted(payload.items()))
        expected = hmac.new(
            self._api_key.encode(), body.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, sig)
