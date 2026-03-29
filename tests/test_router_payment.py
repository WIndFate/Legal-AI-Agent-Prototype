"""Integration tests for /api/payment/* endpoints."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from backend.db.session import get_db
from backend.routers.payment import router

app = FastAPI()
app.include_router(router)


# ---------------------------------------------------------------------------
# Fake DB helpers
# ---------------------------------------------------------------------------


class FakeOrder:
    """Minimal stand-in for the Order model."""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.email = kwargs.get("email", "test@example.com")
        self.contract_text = kwargs.get("contract_text", "第1条 テスト")
        self.input_type = kwargs.get("input_type", "text")
        self.estimated_tokens = kwargs.get("estimated_tokens", 100)
        self.page_estimate = kwargs.get("page_estimate", 1)
        self.pricing_model = kwargs.get("pricing_model", "token_linear")
        self.price_jpy = kwargs.get("price_jpy", 299)
        self.quote_mode = kwargs.get("quote_mode", "exact")
        self.estimate_source = kwargs.get("estimate_source", "raw_text")
        self.temp_upload_token = kwargs.get("temp_upload_token", None)
        self.temp_upload_name = kwargs.get("temp_upload_name", None)
        self.temp_upload_mime_type = kwargs.get("temp_upload_mime_type", None)
        self.target_language = kwargs.get("target_language", "ja")
        self.referral_code_used = kwargs.get("referral_code_used", None)
        self.payment_status = kwargs.get("payment_status", "pending")
        self.paid_at = kwargs.get("paid_at", None)
        self.komoju_session_id = kwargs.get("komoju_session_id", None)
        self.analysis_status = kwargs.get("analysis_status", "waiting")


class _FakeResult:
    def __init__(self, obj=None):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


class FakeSession:
    """Async session mock that stores added objects and fakes queries."""

    def __init__(self, query_result=None):
        self._added = []
        self._query_result = query_result
        self.commit_count = 0

    def add(self, obj):
        self._added.append(obj)
        # Assign a fake id when the model is added
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = uuid.uuid4()

    async def commit(self):
        self.commit_count += 1

    async def refresh(self, obj):
        pass

    async def execute(self, stmt):
        return _FakeResult(self._query_result)


def _override_db(session: FakeSession):
    async def _dep():
        yield session
    return _dep


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_analytics():
    with patch("backend.routers.payment.posthog_capture"):
        yield


@pytest.fixture(autouse=True)
def _mock_quote_context():
    with (
        patch("backend.routers.payment.get_redis", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.payment.load_quote_context", new_callable=AsyncMock, return_value=None),
    ):
        yield


# ---------------------------------------------------------------------------
# POST /api/payment/create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_payment_happy_path():
    """Creating a payment should return order_id and session URL."""
    session = FakeSession()

    app.dependency_overrides[get_db] = _override_db(session)
    try:
        with (
            patch(
                "backend.routers.payment.create_payment_session",
                new_callable=AsyncMock,
                return_value="https://komoju.com/sessions/test123",
            ),
            patch("backend.routers.payment.is_dev_payment_mode", return_value=False),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/payment/create",
                    json={
                        "email": "user@example.com",
                        "contract_text": "第1条 テスト契約",
                        "input_type": "text",
                        "estimated_tokens": 50,
                        "price_jpy": 299,
                        "target_language": "zh-CN",
                    },
                )
        assert resp.status_code == 200
        body = resp.json()
        assert "order_id" in body
        assert body["komoju_session_url"] == "https://komoju.com/sessions/test123"
        assert body["price_jpy"] == 299
        assert body["discount_applied"] == 0
        assert session.commit_count >= 1
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_create_payment_includes_quote_context_in_estimate_snapshot():
    """Payment creation should carry prepayment quote context into the persisted estimate snapshot."""
    session = FakeSession()

    app.dependency_overrides[get_db] = _override_db(session)
    try:
        with (
            patch(
                "backend.routers.payment.create_payment_session",
                new_callable=AsyncMock,
                return_value="https://komoju.com/sessions/test123",
            ),
            patch("backend.routers.payment.is_dev_payment_mode", return_value=False),
            patch(
                "backend.routers.payment.load_quote_context",
                new_callable=AsyncMock,
                return_value={"prepayment_snapshot": {"preview_cost_jpy": 0.043}},
            ),
            patch("backend.routers.payment.build_order_cost_estimate_snapshot") as build_snapshot,
        ):
            build_snapshot.return_value = {"estimate_version": "v1"}
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/payment/create",
                    json={
                        "email": "user@example.com",
                        "contract_text": "第1条 テスト契約",
                        "input_type": "text",
                        "estimated_tokens": 50,
                        "price_jpy": 299,
                        "target_language": "zh-CN",
                        "quote_token": "quote-test-token",
                    },
                )
        assert resp.status_code == 200
        assert build_snapshot.call_args.kwargs["prepayment_quote"] == {"prepayment_snapshot": {"preview_cost_jpy": 0.043}}
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_create_payment_dev_bypass():
    """In dev mode with no KOMOJU key, payment should be auto-marked paid."""
    session = FakeSession()

    app.dependency_overrides[get_db] = _override_db(session)
    try:
        with (
            patch(
                "backend.routers.payment.create_payment_session",
                new_callable=AsyncMock,
                return_value="http://localhost:5173/review/test?dev_payment=true",
            ),
            patch("backend.routers.payment.is_dev_payment_mode", return_value=True),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/payment/create",
                    json={
                        "email": "dev@example.com",
                        "contract_text": "第1条",
                        "input_type": "text",
                        "estimated_tokens": 10,
                        "price_jpy": 299,
                    },
                )
        assert resp.status_code == 200
        body = resp.json()
        assert "order_id" in body
        # In dev bypass, commit is called multiple times (order save + payment mark)
        assert session.commit_count >= 2
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_create_payment_prefers_request_origin_for_frontend_base_url():
    """LAN/mobile browser origins should be used for dev redirect URLs instead of localhost."""
    session = FakeSession()
    create_session_mock = AsyncMock(return_value="http://192.168.3.20:5173/review/test?dev_payment=true")

    app.dependency_overrides[get_db] = _override_db(session)
    try:
        with (
            patch("backend.routers.payment.create_payment_session", new=create_session_mock),
            patch("backend.routers.payment.is_dev_payment_mode", return_value=True),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/payment/create",
                    headers={"origin": "http://192.168.3.20:5173"},
                    json={
                        "email": "dev@example.com",
                        "contract_text": "第1条",
                        "input_type": "text",
                        "estimated_tokens": 10,
                        "price_jpy": 299,
                    },
                )
        assert resp.status_code == 200
        assert create_session_mock.await_args.kwargs["frontend_base_url"] == "http://192.168.3.20:5173"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_create_payment_invalid_email_returns_422():
    """Request with invalid email should return 422."""
    session = FakeSession()
    app.dependency_overrides[get_db] = _override_db(session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/payment/create",
                json={
                    "email": "not-an-email",
                    "contract_text": "第1条",
                    "input_type": "text",
                    "estimated_tokens": 10,
                    "price_jpy": 299,
                },
            )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_create_payment_missing_fields_returns_422():
    """Request missing required fields should return 422."""
    session = FakeSession()
    app.dependency_overrides[get_db] = _override_db(session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/payment/create",
                json={"email": "user@example.com"},
            )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# POST /api/payment/webhook
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_payment_captured_marks_order_paid():
    """Valid webhook with payment.captured should mark order as paid."""
    order = FakeOrder(payment_status="pending")
    order_id = str(order.id)
    session = FakeSession(query_result=order)

    webhook_body = {
        "type": "payment.captured",
        "data": {
            "id": "komoju-pay-123",
            "metadata": {"order_id": order_id},
        },
    }
    raw_body = json.dumps(webhook_body).encode()

    app.dependency_overrides[get_db] = _override_db(session)
    try:
        with patch(
            "backend.routers.payment.verify_webhook",
            new_callable=AsyncMock,
            return_value=webhook_body,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/payment/webhook",
                    content=raw_body,
                    headers={"x-komoju-signature": "test-sig"},
                )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        assert order.payment_status == "paid"
        assert order.paid_at is not None
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_webhook_invalid_signature_returns_401():
    """Invalid webhook signature should return 401."""
    session = FakeSession()
    app.dependency_overrides[get_db] = _override_db(session)
    try:
        with patch(
            "backend.routers.payment.verify_webhook",
            new_callable=AsyncMock,
            return_value=None,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/payment/webhook",
                    content=b"{}",
                    headers={"x-komoju-signature": "bad-sig"},
                )
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_webhook_already_paid_order_is_ignored():
    """Webhook for an already-paid order should return 200 without changing state."""
    order = FakeOrder(payment_status="paid")
    order_id = str(order.id)
    session = FakeSession(query_result=order)

    webhook_body = {
        "type": "payment.captured",
        "data": {
            "id": "komoju-pay-dup",
            "metadata": {"order_id": order_id},
        },
    }

    app.dependency_overrides[get_db] = _override_db(session)
    try:
        with patch(
            "backend.routers.payment.verify_webhook",
            new_callable=AsyncMock,
            return_value=webhook_body,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/payment/webhook",
                    content=json.dumps(webhook_body).encode(),
                    headers={"x-komoju-signature": "test-sig"},
                )
        assert resp.status_code == 200
        # commit should not have been called because order was already paid
        assert session.commit_count == 0
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# GET /api/payment/status/{order_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_payment_status_returns_order_status():
    """Payment status endpoint should return the order's payment status."""
    order = FakeOrder(payment_status="paid")
    session = FakeSession(query_result=order)

    app.dependency_overrides[get_db] = _override_db(session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/payment/status/{order.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "paid"
        assert body["order_id"] == str(order.id)
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_payment_status_not_found_returns_404():
    """Payment status for non-existent order should return 404."""
    session = FakeSession(query_result=None)

    app.dependency_overrides[get_db] = _override_db(session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/payment/status/{uuid.uuid4()}")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
