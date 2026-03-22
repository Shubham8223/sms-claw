"""Telegram tool — send messages via Bot API."""

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
async def send_telegram(chat_id: str, message: str) -> str:
    """
    Send a Telegram message. 'chat_id' is a numeric ID or @username.
    Always confirm with the user before sending unless they explicitly asked.
    """
    if not _s.telegram_bot_token:
        return "Telegram not configured. Set TELEGRAM_BOT_TOKEN."
    try:
        url = f"https://api.telegram.org/bot{_s.telegram_bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
            )
            resp.raise_for_status()
            msg_id = resp.json()["result"]["message_id"]
            log.info("telegram_sent", chat_id=chat_id, msg_id=msg_id)
            return f"Telegram message sent to {chat_id}. ID: {msg_id}"
    except Exception as exc:
        log.error("telegram_error", chat_id=chat_id, error=str(exc), exc_info=True)
        return f"Telegram failed: {exc}"
