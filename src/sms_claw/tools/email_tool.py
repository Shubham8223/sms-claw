"""Email tool — async SMTP."""

from __future__ import annotations

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
from langchain_core.tools import tool

from sms_claw.core.config import get_settings
from sms_claw.core.logging import get_logger
from sms_claw.tools.registry import register_tool

log = get_logger(__name__)
_s = get_settings()


@register_tool
@tool
async def send_email(to: str, subject: str, body: str) -> str:
    """
    Send an email. Always confirm with the user before sending unless they explicitly asked.
    """
    if not _s.smtp_username or not _s.smtp_password:
        return "Email not configured. Set SMTP_USERNAME and SMTP_PASSWORD."
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = _s.email_from or _s.smtp_username
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        await aiosmtplib.send(
            msg,
            hostname=_s.smtp_host,
            port=_s.smtp_port,
            username=_s.smtp_username,
            password=_s.smtp_password,
            start_tls=True,
        )
        log.info("email_sent", to=to, subject=subject)
        return f"Email sent to {to} — '{subject}'"
    except Exception as exc:
        log.error("email_error", to=to, error=str(exc), exc_info=True)
        return f"Email failed: {exc}"
