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
