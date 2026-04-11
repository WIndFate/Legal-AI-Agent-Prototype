from types import SimpleNamespace

import pytest

from backend.services import payment


@pytest.fixture(autouse=True)
def clear_payment_method_cache():
    payment.get_komoju_payment_methods.cache_clear()
    yield
    payment.get_komoju_payment_methods.cache_clear()


def test_get_komoju_payment_methods_reads_json_file(tmp_path, monkeypatch):
    config_path = tmp_path / "komoju_payment_methods.json"
    config_path.write_text(
        """
        {
          "session_payment_types": ["credit_card", "wechatpay", "alipay", "unionpay", "paypay"]
        }
        """,
        encoding="utf-8",
    )

    monkeypatch.setattr(
        payment,
        "get_settings",
        lambda: SimpleNamespace(KOMOJU_PAYMENT_METHODS_FILE=str(config_path)),
    )

    assert payment.get_komoju_session_payment_types() == [
        "credit_card",
        "wechatpay",
        "alipay",
        "unionpay",
        "paypay",
    ]


@pytest.mark.asyncio
async def test_create_payment_session_uses_configured_payment_types(monkeypatch):
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
            KOMOJU_PAYMENT_METHODS_FILE="unused",
        ),
    )
    monkeypatch.setattr(
        payment,
        "get_komoju_session_payment_types",
        lambda: ["credit_card", "wechatpay", "alipay", "unionpay", "paypay"],
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
    assert posted["json"]["payment_types"] == [
        "credit_card",
        "wechatpay",
        "alipay",
        "unionpay",
        "paypay",
    ]
