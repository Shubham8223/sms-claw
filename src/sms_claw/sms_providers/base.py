"""Abstract SMS provider interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class InboundMessage:
    """Normalised inbound SMS — provider-agnostic."""
    provider: str
    from_number: str       # E.164 e.g. +919876543210
    to_number: str
    body: str
    message_id: str
    raw: dict = field(default_factory=dict)


@dataclass
class OutboundResult:
    success: bool
    message_id: str | None = None
    error: str | None = None


class SMSProviderBase(ABC):
    """Every SMS adapter must implement these three methods."""

    provider_name: str = "base"

    @abstractmethod
    async def send(self, to: str, body: str) -> OutboundResult: ...

    @abstractmethod
    def parse_inbound(self, payload: dict) -> InboundMessage: ...

    @abstractmethod
    def verify_webhook(self, request_url: str, payload: dict, headers: dict) -> bool: ...
