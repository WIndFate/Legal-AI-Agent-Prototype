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
        self.target_language = kwargs.get("target_language", "ja")
        self.referral_code_used = kwargs.get("referral_code_used", None)
        self.payment_status = kwargs.get("payment_status", "pending")
        self.paid_at = kwargs.get("paid_at", None)
        self.komoju_session_id = kwargs.get("komoju_session_id", None)
        self.analysis_status = kwargs.get("analysis_status", "waiting")
        self.client_ip = kwargs.get("client_ip", "127.0.0.1")
        self.access_token = kwargs.get("access_token", "access-token-123")
        self.share_token = kwargs.get("share_token", None)


class _FakeResult:
    def __init__(self, obj=None):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


class FakeSession:
    """Async session mock that stores added objects and fakes queries."""

    def __init__(self, query_result=None, get_result=None, execute_result=None):
        self._added = []
        self._get_result = query_result if get_result is None else get_result
        self._execute_result = query_result if execute_result is None else execute_result
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

    async def get(self, model, key):
        return self._get_result

    async def execute(self, stmt):
        return _FakeResult(self._execute_result)


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
        patch("backend.routers.payment.abuse_record_payment", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.payment.record_webhook_event", new_callable=AsyncMock, return_value=True),
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
            patch(
                "backend.routers.payment.load_quote_context",
                new_callable=AsyncMock,
                return_value={"content_hash": "hash-text-123", "is_contract": True},
            ),
            patch("backend.routers.payment.build_contract_content_hash", return_value="hash-text-123"),
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
                        "quote_mode": "exact",
                        "quote_token": "quote-test-token",
                        "target_language": "zh-CN",
                    },
                )
        assert resp.status_code == 200
        body = resp.json()
        assert "order_id" in body
        assert "access_token" in body
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
                return_value={
                    "content_hash": "hash-text-234",
                    "is_contract": True,
                    "prepayment_snapshot": {"preview_cost_jpy": 0.043},
                },
            ),
            patch("backend.routers.payment.build_contract_content_hash", return_value="hash-text-234"),
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
        assert build_snapshot.call_args.kwargs["prepayment_quote"] == {
            "content_hash": "hash-text-234",
            "is_contract": True,
            "prepayment_snapshot": {"preview_cost_jpy": 0.043},
        }
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_create_payment_rejects_missing_exact_quote_context():
    """Exact quotes must be backed by a live quote_token context before payment."""
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
                return_value=None,
            ),
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
                        "quote_mode": "exact",
                        "quote_token": "quote-test-token",
                    },
                )
        assert resp.status_code == 409
        assert "upload the contract again" in resp.json()["detail"]
        assert session.commit_count == 0
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_create_payment_rejects_non_contract_exact_quote():
    """Exact quotes flagged as non-contract must be blocked server-side before order creation."""
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
                return_value={
                    "content_hash": "d8f16f31f4f2df67f7d8f6b9f6b73f7d5bdfb1779a40d7f6b7c72f3f6b754f15",
                    "is_contract": False,
                },
            ),
            patch(
                "backend.routers.payment.build_contract_content_hash",
                return_value="d8f16f31f4f2df67f7d8f6b9f6b73f7d5bdfb1779a40d7f6b7c72f3f6b754f15",
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/payment/create",
                    json={
                        "email": "user@example.com",
                        "contract_text": "これは会議メモです。",
                        "input_type": "text",
                        "estimated_tokens": 50,
                        "price_jpy": 299,
                        "target_language": "zh-CN",
                        "quote_mode": "exact",
                        "quote_token": "quote-test-token",
                    },
                )
        assert resp.status_code == 409
        assert "non-contract material" in resp.json()["detail"]
        assert session.commit_count == 0
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_create_payment_rejects_non_contract_image_exact_quote():
    """Image uploads OCR'd at upload time must still be blocked server-side when flagged non-contract."""
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
                return_value={
                    "content_hash": "hash-image-123",
                    "is_contract": False,
                    "prepayment_snapshot": {"ocr_cost_jpy": 0.75},
                },
            ),
            patch("backend.routers.payment.build_contract_content_hash", return_value="hash-image-123"),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/payment/create",
                    json={
                        "email": "user@example.com",
                        "contract_text": "これは会議メモです。",
                        "input_type": "image",
                        "estimated_tokens": 50,
                        "price_jpy": 299,
                        "target_language": "zh-CN",
                        "quote_mode": "exact",
                        "quote_token": "quote-test-token",
                    },
                )
        assert resp.status_code == 409
        assert "non-contract material" in resp.json()["detail"]
        assert session.commit_count == 0
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_create_payment_allows_image_exact_quote_with_contract_context():
    """Image uploads that passed upload-time OCR should create payments like any other exact quote."""
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
                return_value={
                    "content_hash": "hash-image-456",
                    "is_contract": True,
                    "prepayment_snapshot": {"ocr_cost_jpy": 0.75},
                },
            ),
            patch("backend.routers.payment.build_contract_content_hash", return_value="hash-image-456"),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/payment/create",
                    json={
                        "email": "user@example.com",
                        "contract_text": "第1条 テスト契約",
                        "input_type": "image",
                        "estimated_tokens": 50,
                        "price_jpy": 299,
                        "target_language": "zh-CN",
                        "quote_mode": "exact",
                        "quote_token": "quote-test-token",
                    },
                )
        assert resp.status_code == 200
        assert session.commit_count >= 1
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
            patch(
                "backend.routers.payment.load_quote_context",
                new_callable=AsyncMock,
                return_value={"content_hash": "hash-dev-123", "is_contract": True},
            ),
            patch("backend.routers.payment.build_contract_content_hash", return_value="hash-dev-123"),
            patch("backend.routers.payment.send_payment_confirmation_email", new_callable=AsyncMock) as send_email_mock,
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
                        "quote_mode": "exact",
                        "quote_token": "quote-dev-token",
                    },
                )
        assert resp.status_code == 200
        body = resp.json()
        assert "order_id" in body
        # In dev bypass, commit is called multiple times (order save + payment mark)
        assert session.commit_count >= 2
        send_email_mock.assert_awaited_once()
        assert send_email_mock.await_args.args[0] == "dev@example.com"
        assert send_email_mock.await_args.args[2] == "ja"
        assert send_email_mock.await_args.args[3] == 299
        assert send_email_mock.await_args.args[4]
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
            patch(
                "backend.routers.payment.load_quote_context",
                new_callable=AsyncMock,
                return_value={"content_hash": "hash-dev-234", "is_contract": True},
            ),
            patch("backend.routers.payment.build_contract_content_hash", return_value="hash-dev-234"),
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
                        "quote_mode": "exact",
                        "quote_token": "quote-lan-token",
                    },
                )
        assert resp.status_code == 200
        assert create_session_mock.await_args.kwargs["frontend_base_url"] == "http://192.168.3.20:5173"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_create_payment_ignores_internal_backend_host_for_frontend_base_url():
    """Internal container hostnames should never leak into browser redirect URLs."""
    session = FakeSession()
    create_session_mock = AsyncMock(return_value="http://localhost:5173/review/test?dev_payment=true")

    app.dependency_overrides[get_db] = _override_db(session)
    try:
        with (
            patch("backend.routers.payment.create_payment_session", new=create_session_mock),
            patch("backend.routers.payment.is_dev_payment_mode", return_value=True),
            patch(
                "backend.routers.payment.load_quote_context",
                new_callable=AsyncMock,
                return_value={"content_hash": "hash-dev-345", "is_contract": True},
            ),
            patch("backend.routers.payment.build_contract_content_hash", return_value="hash-dev-345"),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/payment/create",
                    headers={"host": "backend:8000"},
                    json={
                        "email": "dev@example.com",
                        "contract_text": "第1条",
                        "input_type": "text",
                        "estimated_tokens": 10,
                        "price_jpy": 299,
                        "quote_mode": "exact",
                        "quote_token": "quote-backend-token",
                    },
                )
        assert resp.status_code == 200
        assert create_session_mock.await_args.kwargs["frontend_base_url"] == "http://localhost:5173"
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


@pytest.mark.asyncio
async def test_retry_payment_reopens_checkout_for_terminal_order():
    """Existing terminal unpaid orders should get a fresh checkout session without creating a new order."""
    order = FakeOrder(payment_status="cancelled", price_jpy=480)
    session = FakeSession(query_result=order)

    app.dependency_overrides[get_db] = _override_db(session)
    try:
        with patch(
            "backend.routers.payment.create_payment_session",
            new_callable=AsyncMock,
            return_value="https://komoju.com/sessions/retry-123",
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(f"/api/payment/{order.id}/retry")
        assert resp.status_code == 200
        body = resp.json()
        assert body["order_id"] == str(order.id)
        assert body["komoju_session_url"] == "https://komoju.com/sessions/retry-123"
        assert body["access_token"] == order.access_token
        assert body["price_jpy"] == 480
        assert order.payment_status == "pending"
        assert session.commit_count == 1
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_retry_payment_rejects_missing_contract_data():
    """Retry should fail fast when the contract text is no longer available."""
    order = FakeOrder(contract_text=None, payment_status="cancelled")
    session = FakeSession(get_result=order)

    app.dependency_overrides[get_db] = _override_db(session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/payment/{order.id}/retry")
        assert resp.status_code == 410
        assert "uploaded contract is no longer available" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_retry_payment_rejects_paid_order():
    """Paid orders must not reopen checkout."""
    order = FakeOrder(payment_status="paid")
    session = FakeSession(get_result=order)

    app.dependency_overrides[get_db] = _override_db(session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/payment/{order.id}/retry")
        assert resp.status_code == 409
        assert resp.json()["detail"] == "Payment already completed"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_retry_payment_rejects_unsupported_status():
    """Retry should be unavailable for orders outside pending/failed/cancelled."""
    order = FakeOrder(payment_status="refunded")
    session = FakeSession(get_result=order)

    app.dependency_overrides[get_db] = _override_db(session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/payment/{order.id}/retry")
        assert resp.status_code == 409
        assert resp.json()["detail"] == "Payment retry is not available for this order"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_retry_payment_missing_order_returns_404():
    """Retrying a missing order should return 404."""
    session = FakeSession(get_result=None)

    app.dependency_overrides[get_db] = _override_db(session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/payment/{uuid.uuid4()}/retry")
        assert resp.status_code == 404
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
        with (
            patch(
                "backend.routers.payment.verify_webhook",
                new_callable=AsyncMock,
                return_value=(webhook_body, None),
            ),
            patch("backend.routers.payment.send_payment_confirmation_email", new_callable=AsyncMock) as send_email_mock,
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
        send_email_mock.assert_awaited_once_with(
            order.email,
            order_id,
            order.target_language,
            order.price_jpy,
            order.access_token,
        )
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
            return_value=(None, "invalid_signature"),
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
async def test_webhook_replay_is_acknowledged_without_side_effects():
    """Replayed webhook events should return 200 but skip DB writes and email."""
    order = FakeOrder(payment_status="pending")
    order_id = str(order.id)
    session = FakeSession(query_result=order)

    webhook_body = {
        "id": "evt_replay_123",
        "type": "payment.captured",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data": {
            "id": "komoju-pay-replay",
            "metadata": {"order_id": order_id},
        },
    }

    app.dependency_overrides[get_db] = _override_db(session)
    try:
        with (
            patch(
                "backend.routers.payment.verify_webhook",
                new_callable=AsyncMock,
                return_value=(webhook_body, None),
            ),
            patch(
                "backend.routers.payment.record_webhook_event",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("backend.routers.payment.send_payment_confirmation_email", new_callable=AsyncMock) as send_email_mock,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/payment/webhook",
                    content=json.dumps(webhook_body).encode(),
                    headers={"x-komoju-signature": "test-sig"},
                )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        assert order.payment_status == "pending"
        assert session.commit_count == 0
        send_email_mock.assert_not_awaited()
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_webhook_returns_503_when_replay_guard_unavailable():
    """Webhook processing should fail closed when replay protection storage is unavailable."""
    session = FakeSession()
    webhook_body = {
        "id": "evt_storage_123",
        "type": "payment.captured",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data": {"id": "komoju-pay-123", "metadata": {"order_id": str(uuid.uuid4())}},
    }

    app.dependency_overrides[get_db] = _override_db(session)
    try:
        with (
            patch(
                "backend.routers.payment.verify_webhook",
                new_callable=AsyncMock,
                return_value=(webhook_body, None),
            ),
            patch(
                "backend.routers.payment.record_webhook_event",
                new_callable=AsyncMock,
                side_effect=RuntimeError("redis_down"),
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/payment/webhook",
                    content=json.dumps(webhook_body).encode(),
                    headers={"x-komoju-signature": "test-sig"},
                )
        assert resp.status_code == 503
        assert resp.json()["detail"] == "Webhook replay protection unavailable"
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
        with (
            patch(
                "backend.routers.payment.verify_webhook",
                new_callable=AsyncMock,
                return_value=(webhook_body, None),
            ),
            patch("backend.routers.payment.send_payment_confirmation_email", new_callable=AsyncMock) as send_email_mock,
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
        send_email_mock.assert_not_awaited()
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("event_type", "expected_status"),
    [
        ("payment.failed", "failed"),
        ("payment.cancelled", "cancelled"),
        ("payment.expired", "cancelled"),
    ],
)
async def test_webhook_terminal_events_update_payment_status(event_type: str, expected_status: str):
    """Terminal KOMOJU payment events should map into the persisted order payment status."""
    order = FakeOrder(payment_status="pending")
    order_id = str(order.id)
    session = FakeSession(query_result=order)

    webhook_body = {
        "type": event_type,
        "data": {
            "id": f"komoju-{event_type}",
            "metadata": {"order_id": order_id},
        },
    }

    app.dependency_overrides[get_db] = _override_db(session)
    try:
        with patch(
            "backend.routers.payment.verify_webhook",
            new_callable=AsyncMock,
            return_value=(webhook_body, None),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/payment/webhook",
                    content=json.dumps(webhook_body).encode(),
                    headers={"x-komoju-signature": "test-sig"},
                )
        assert resp.status_code == 200
        assert order.payment_status == expected_status
        assert order.komoju_session_id == f"komoju-{event_type}"
        assert session.commit_count == 1
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", ["payment.failed", "payment.cancelled", "payment.expired"])
async def test_webhook_terminal_events_do_not_downgrade_paid_order(event_type: str):
    """Once paid, later terminal webhook events should be ignored."""
    order = FakeOrder(payment_status="paid")
    order_id = str(order.id)
    session = FakeSession(query_result=order)

    webhook_body = {
        "type": event_type,
        "data": {
            "id": f"komoju-{event_type}",
            "metadata": {"order_id": order_id},
        },
    }

    app.dependency_overrides[get_db] = _override_db(session)
    try:
        with patch(
            "backend.routers.payment.verify_webhook",
            new_callable=AsyncMock,
            return_value=(webhook_body, None),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/payment/webhook",
                    content=json.dumps(webhook_body).encode(),
                    headers={"x-komoju-signature": "test-sig"},
                )
        assert resp.status_code == 200
        assert order.payment_status == "paid"
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
