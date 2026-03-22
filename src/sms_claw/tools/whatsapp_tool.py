"""WhatsApp tool — Meta Cloud API."""

from __future__ import annotations

import httpx
from langchain_core.tools import tool

from sms_claw.core.config import get_settings
from sms_claw.core.logging import get_logger
from sms_claw.tools.registry import register_tool

log = get_logger(__name__)
_s = get_settings()


@register_tool
@tool
async def send_whatsapp(to: str, message: str) -> str:
    """
    Send a WhatsApp message. 'to' must be E.164 (+919876543210).
    Always confirm with the user before sending unless they explicitly asked.
    """
    if not _s.whatsapp_api_token or not _s.whatsapp_phone_number_id:
        return "WhatsApp not configured. Set WHATSAPP_API_TOKEN and WHATSAPP_PHONE_NUMBER_ID."
    try:
        url = f"https://graph.facebook.com/v19.0/{_s.whatsapp_phone_number_id}/messages"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {_s.whatsapp_api_token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": to.lstrip("+"),
                    "type": "text",
                    "text": {"body": message},
                },
            )
            resp.raise_for_status()
            msg_id = resp.json()["messages"][0]["id"]
            log.info("whatsapp_sent", to=to, msg_id=msg_id)
            return f"WhatsApp sent to {to}. ID: {msg_id}"
    except Exception as exc:
        log.error("whatsapp_error", to=to, error=str(exc), exc_info=True)
        return f"WhatsApp failed: {exc}"
