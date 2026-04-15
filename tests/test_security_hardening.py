"""Regression coverage for the second-round P0-1 / P0-5 hardening fixes."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.services.abuse_guard import (
    _uploads_key,
    record_ocr_upload,
    rollback_ocr_upload,
)
from backend.services.quote_guard import extract_client_ip


def _fake_request(headers: dict[str, str], peer: str | None = "10.0.0.1") -> SimpleNamespace:
    lowered = {k.lower(): v for k, v in headers.items()}
    return SimpleNamespace(
        headers=SimpleNamespace(get=lambda key, default="": lowered.get(key.lower(), default)),
        client=SimpleNamespace(host=peer) if peer else None,
    )


def test_extract_client_ip_prefers_fly_header():
    req = _fake_request({"fly-client-ip": "203.0.113.5", "x-forwarded-for": "1.2.3.4, 5.6.7.8"})
    assert extract_client_ip(req) == "203.0.113.5"


def test_extract_client_ip_uses_rightmost_xff_when_no_fly_header():
    # Leftmost entry is client-controlled and was the previous (spoofable) behavior.
    req = _fake_request({"x-forwarded-for": "evil-spoof, 5.6.7.8, 9.10.11.12"})
    assert extract_client_ip(req) == "9.10.11.12"


def test_extract_client_ip_falls_back_to_socket_peer():
    req = _fake_request({}, peer="127.0.0.1")
    assert extract_client_ip(req) == "127.0.0.1"


@pytest.mark.asyncio
async def test_rollback_never_drives_counter_below_zero(monkeypatch):
    """Safe-decr Lua script: DECR only when current value > 0."""

    class FakeRedis:
        def __init__(self):
            self.store: dict[str, int] = {}

        async def incr(self, key):
            self.store[key] = self.store.get(key, 0) + 1
            return self.store[key]

        async def expire(self, key, seconds):  # noqa: ARG002
            return True

        async def eval(self, script, numkeys, *keys):  # noqa: ARG002
            key = keys[0]
            current = self.store.get(key, 0)
            if current > 0:
                self.store[key] = current - 1
                return self.store[key]
            return 0

    redis = FakeRedis()
    ip = "198.51.100.1"

    # Simulate TTL expiry between INCR and rollback by clearing the key.
    await record_ocr_upload(redis, ip)
    redis.store.pop(_uploads_key(ip), None)
    await rollback_ocr_upload(redis, ip)
    assert redis.store.get(_uploads_key(ip), 0) == 0  # never -1


@pytest.mark.asyncio
async def test_record_ocr_upload_raises_503_when_redis_none():
    with pytest.raises(HTTPException) as excinfo:
        await record_ocr_upload(None, "198.51.100.1")
    assert excinfo.value.status_code == 503


@pytest.mark.asyncio
async def test_create_payment_rejects_non_exact_with_missing_context():
    """Non-exact payments must not bypass price validation when no quote is cached."""
    from backend.db.session import get_db
    from tests.test_router_payment import FakeSession, _override_db

    session = FakeSession()
    app.dependency_overrides[get_db] = _override_db(session)
    try:
        with (
            patch(
                "backend.routers.payment.load_quote_context",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "backend.routers.payment.load_upload_quote_context",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/payment/create",
                    json={
                        "email": "user@example.com",
                        "contract_text": "第1条 テスト",
                        "input_type": "pdf",
                        "estimated_tokens": 8000,
                        "price_jpy": 1,
                        "quote_mode": "staged",
                        "upload_token": "tok-expired",
                        "target_language": "ja",
                    },
                )
        assert resp.status_code == 409
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_create_payment_rejects_non_exact_with_tampered_price():
    """Non-exact payments must reject forged price when upload context is cached."""
    from backend.db.session import get_db
    from tests.test_router_payment import FakeSession, _override_db

    session = FakeSession()
    app.dependency_overrides[get_db] = _override_db(session)
    try:
        with (
            patch(
                "backend.routers.payment.load_quote_context",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "backend.routers.payment.load_upload_quote_context",
                new_callable=AsyncMock,
                return_value={
                    "is_contract": True,
                    "price_jpy": 1500,
                    "estimated_tokens": 8000,
                },
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/payment/create",
                    json={
                        "email": "user@example.com",
                        "contract_text": "第1条 テスト",
                        "input_type": "pdf",
                        "estimated_tokens": 8000,
                        "price_jpy": 1,
                        "quote_mode": "staged",
                        "upload_token": "tok-valid",
                        "target_language": "ja",
                    },
                )
        assert resp.status_code == 409
        assert "price" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_create_payment_rejects_tampered_price():
    """Client cannot forge a lower price_jpy than the server-signed quote."""
    from backend.db.session import get_db
    from tests.test_router_payment import FakeSession, _override_db

    session = FakeSession()
    app.dependency_overrides[get_db] = _override_db(session)
    try:
        with (
            patch(
                "backend.routers.payment.load_quote_context",
                new_callable=AsyncMock,
                return_value={
                    "content_hash": "hash-xyz",
                    "is_contract": True,
                    "price_jpy": 1500,  # server-authoritative
                    "estimated_tokens": 8000,
                },
            ),
            patch("backend.routers.payment.build_contract_content_hash", return_value="hash-xyz"),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/payment/create",
                    json={
                        "email": "user@example.com",
                        "contract_text": "第1条 テスト",
                        "input_type": "text",
                        "estimated_tokens": 8000,
                        "price_jpy": 1,  # forged
                        "quote_mode": "exact",
                        "quote_token": "tok-xyz",
                        "target_language": "ja",
                    },
                )
        assert resp.status_code == 409
        assert "price" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_db, None)
