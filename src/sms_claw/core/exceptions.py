"""
Domain exceptions.

Rules
-----
- Raise domain exceptions in services/repositories.
- Translate them to HTTP responses in api/routers ONLY.
- Never import FastAPI into services or repositories.
"""
from __future__ import annotations


class DispatchError(Exception):
    """Base for all application errors."""
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.__class__.message
        super().__init__(self.message)


# ── Auth / Security ───────────────────────────────────────────────────────────

class PhoneNotAllowedError(DispatchError):
    message = "Phone number is not on the allowlist."


class NotEnrolledError(DispatchError):
    message = "Phone number has not completed OTP enrollment."


class InvalidOTPError(DispatchError):
    message = "OTP is invalid or has expired."


class RateLimitExceededError(DispatchError):
    message = "Rate limit exceeded. Try again next hour."


class WebhookSignatureError(DispatchError):
    message = "Webhook signature verification failed."


# ── Domain ────────────────────────────────────────────────────────────────────

class UserNotFoundError(DispatchError):
    message = "User not found."


class SessionNotFoundError(DispatchError):
    message = "Session not found."


# ── Infrastructure ────────────────────────────────────────────────────────────

class SMSDeliveryError(DispatchError):
    message = "Failed to deliver SMS."


class LLMError(DispatchError):
    message = "LLM call failed."


class ToolExecutionError(DispatchError):
    message = "Tool execution failed."


class MemoryError(DispatchError):  # noqa: A001 — intentional shadow
    message = "Memory operation failed."
