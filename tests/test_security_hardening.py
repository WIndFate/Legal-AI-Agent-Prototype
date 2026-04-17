"""Regression coverage for the second-round P0-1 / P0-5 hardening fixes."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from backend.main import SecurityHeadersMiddleware, app
from backend.services.abuse_guard import (
    _uploads_key,
    check_ocr_allowed,
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
    with patch(
        "backend.services.quote_guard.get_settings",
        return_value=SimpleNamespace(is_production=True),
    ):
        assert extract_client_ip(req) == "203.0.113.5"


def test_extract_client_ip_ignores_xff_in_production_without_fly_header():
    req = _fake_request({"x-forwarded-for": "evil-spoof, 5.6.7.8, 9.10.11.12"})
    with (
        patch(
            "backend.services.quote_guard.get_settings",
            return_value=SimpleNamespace(is_production=True),
        ),
        patch("backend.services.quote_guard.logger.warning") as mock_warning,
    ):
        assert extract_client_ip(req) == "10.0.0.1"
    mock_warning.assert_called_once_with("fly_client_ip_missing_in_prod")


def test_extract_client_ip_returns_unknown_when_prod_has_no_source():
    req = _fake_request({}, peer=None)
    with (
        patch(
            "backend.services.quote_guard.get_settings",
            return_value=SimpleNamespace(is_production=True),
        ),
        patch("backend.services.quote_guard.logger.warning") as mock_warning,
    ):
        assert extract_client_ip(req) == "unknown"
    mock_warning.assert_called_once_with("fly_client_ip_missing_in_prod")


def test_extract_client_ip_uses_leftmost_xff_in_development():
    req = _fake_request({"x-forwarded-for": "203.0.113.9, 172.19.0.3"})
    with patch(
        "backend.services.quote_guard.get_settings",
        return_value=SimpleNamespace(is_production=False),
    ):
        assert extract_client_ip(req) == "203.0.113.9"


def test_extract_client_ip_falls_back_to_socket_peer():
    req = _fake_request({}, peer="127.0.0.1")
    with patch(
        "backend.services.quote_guard.get_settings",
        return_value=SimpleNamespace(is_production=False),
    ):
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
async def test_check_ocr_allowed_raises_503_when_redis_none():
    with pytest.raises(HTTPException) as excinfo:
        await check_ocr_allowed(None, "198.51.100.1")
    assert excinfo.value.status_code == 503


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


@pytest.mark.asyncio
async def test_security_headers_middleware_sets_referrer_policy_no_referrer():
    """Every response must carry `Referrer-Policy: no-referrer` so the browser
    never ships `#t=<token>` or `?s=<share_token>` on outbound requests."""
    probe = FastAPI()
    probe.add_middleware(SecurityHeadersMiddleware)

    @probe.get("/probe")
    async def _probe():
        return {"ok": True}

    transport = ASGITransport(app=probe)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/probe")

    assert resp.status_code == 200
    assert resp.headers["referrer-policy"] == "no-referrer"


@pytest.mark.asyncio
async def test_security_headers_middleware_preserves_route_referrer_policy():
    """If a route sets its own Referrer-Policy (e.g., stricter), the middleware
    must not stomp it — setdefault preserves route-level intent."""
    probe = FastAPI()
    probe.add_middleware(SecurityHeadersMiddleware)

    @probe.get("/custom")
    async def _custom():
        from fastapi.responses import JSONResponse
        return JSONResponse({"ok": True}, headers={"Referrer-Policy": "same-origin"})

    transport = ASGITransport(app=probe)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/custom")

    assert resp.status_code == 200
    assert resp.headers["referrer-policy"] == "same-origin"
