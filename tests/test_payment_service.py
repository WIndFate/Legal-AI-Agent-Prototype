import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.services import payment


@pytest.mark.asyncio
async def test_create_payment_session_omits_payment_types(monkeypatch):
    """KOMOJU session should NOT include payment_types so the merchant account controls availability."""
    posted = {}

    class FakeResponse:
        status_code = 200
        text = ""
        is_error = False

        def raise_for_status(self):
            return None

        def json(self):
            return {"session_url": "https://komoju.test/session"}

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, auth, json):
            posted["url"] = url
            posted["auth"] = auth
            posted["json"] = json
            return FakeResponse()

    monkeypatch.setattr(
        payment,
        "get_settings",
        lambda: SimpleNamespace(
            KOMOJU_SECRET_KEY="sk_test_example",
            FRONTEND_URL="https://contractguard-app.vercel.app",
            is_development=False,
            uses_local_frontend_url=lambda: False,
        ),
    )
    monkeypatch.setattr(payment.httpx, "AsyncClient", FakeAsyncClient)

    session_url = await payment.create_payment_session(
        order_id="test-order-id",
        amount_jpy=200,
        email="user@example.com",
        frontend_base_url="https://contractguard-app.vercel.app",
    )

    assert session_url == "https://komoju.test/session"
    assert posted["url"] == "https://komoju.com/api/v1/sessions"
    assert "payment_types" not in posted["json"]
    assert posted["json"]["amount"] == 200
    assert posted["json"]["currency"] == "JPY"
    assert posted["json"]["metadata"] == {"order_id": "test-order-id"}


@pytest.mark.asyncio
async def test_verify_webhook_accepts_recent_signed_event(monkeypatch):
    """A correctly signed, recent webhook should be accepted."""
    event = {
        "id": "evt_recent_123",
        "type": "payment.captured",
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "data": {"metadata": {"order_id": "test-order-id"}},
    }
    payload = json.dumps(event).encode()
    signature = hmac.new(b"whsec_test", payload, hashlib.sha256).hexdigest()

    monkeypatch.setattr(
        payment,
        "get_settings",
        lambda: SimpleNamespace(
            KOMOJU_WEBHOOK_SECRET="whsec_test",
            is_development=False,
        ),
    )

    verified, reason = await payment.verify_webhook(payload, signature)
    assert verified == event
    assert reason is None


@pytest.mark.asyncio
async def test_verify_webhook_accepts_stale_event_for_replay_guard(monkeypatch):
    """Older valid webhook events should be accepted and deduplicated by event id."""
    event = {
        "id": "evt_old_123",
        "type": "payment.captured",
        "created_at": (
            datetime.now(timezone.utc) - timedelta(hours=2)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "data": {"metadata": {"order_id": "test-order-id"}},
    }
    payload = json.dumps(event).encode()
    signature = hmac.new(b"whsec_test", payload, hashlib.sha256).hexdigest()

    monkeypatch.setattr(
        payment,
        "get_settings",
        lambda: SimpleNamespace(
            KOMOJU_WEBHOOK_SECRET="whsec_test",
            is_development=False,
        ),
    )

    verified, reason = await payment.verify_webhook(payload, signature)
    assert verified == event
    assert reason is None


@pytest.mark.asyncio
async def test_verify_webhook_rejects_event_far_in_future(monkeypatch):
    """Webhook events too far in the future should still be rejected."""
    event = {
        "id": "evt_future_123",
        "type": "payment.captured",
        "created_at": (
            datetime.now(timezone.utc) + timedelta(minutes=6)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "data": {"metadata": {"order_id": "test-order-id"}},
    }
    payload = json.dumps(event).encode()
    signature = hmac.new(b"whsec_test", payload, hashlib.sha256).hexdigest()

    monkeypatch.setattr(
        payment,
        "get_settings",
        lambda: SimpleNamespace(
            KOMOJU_WEBHOOK_SECRET="whsec_test",
            is_development=False,
        ),
    )

    verified, reason = await payment.verify_webhook(payload, signature)
    assert verified is None
    assert reason == "event_created_at_in_future"
