"""Shared pytest fixtures."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from sms_claw.sms_providers.base import InboundMessage, OutboundResult, SMSProviderBase

# ── Infrastructure mocks ───────────────────────────────────────────────────────


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock(return_value=True)
    r.setex = AsyncMock(return_value=True)
    r.delete = AsyncMock(return_value=1)
    r.incr = AsyncMock(return_value=1)
    r.expire = AsyncMock(return_value=True)
    r.ping = AsyncMock(return_value=True)
    return r


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    return db


# ── Mock SMS provider ─────────────────────────────────────────────────────────


class _MockProvider(SMSProviderBase):
    provider_name = "mock"

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, to: str, body: str) -> OutboundResult:
        self.sent.append({"to": to, "body": body})
        return OutboundResult(success=True, message_id="mock-001")

    def parse_inbound(self, payload: dict) -> InboundMessage:
        return InboundMessage(
            provider="mock",
            from_number=payload.get("from", "+919999999999"),
            to_number="+910000000000",
            body=payload.get("body", ""),
            message_id="mock-in-001",
            raw=payload,
        )

    def verify_webhook(self, request_url: str, payload: dict, headers: dict) -> bool:
        return True


@pytest.fixture
def mock_provider():
    return _MockProvider()


# ── Async HTTP test client ─────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client():
    from sms_claw.api.app import create_app

    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as c:
        yield c
