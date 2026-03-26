"""Integration tests for POST /api/review/stream endpoint."""

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from backend.db.session import get_db
from backend.routers.review import router

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
        self.contract_text = kwargs.get("contract_text", "第1条 テスト契約")
        self.input_type = kwargs.get("input_type", "text")
        self.estimated_tokens = kwargs.get("estimated_tokens", 50)
        self.page_estimate = kwargs.get("page_estimate", 1)
        self.price_tier = kwargs.get("price_tier", "basic")
        self.price_jpy = kwargs.get("price_jpy", 299)
        self.quote_mode = kwargs.get("quote_mode", "exact")
        self.estimate_source = kwargs.get("estimate_source", "raw_text")
        self.temp_upload_token = kwargs.get("temp_upload_token", None)
        self.temp_upload_name = kwargs.get("temp_upload_name", None)
        self.temp_upload_mime_type = kwargs.get("temp_upload_mime_type", None)
        self.target_language = kwargs.get("target_language", "zh-CN")
        self.referral_code_used = kwargs.get("referral_code_used", None)
        self.payment_status = kwargs.get("payment_status", "paid")
        self.analysis_status = kwargs.get("analysis_status", "waiting")
        self.contract_deleted_at = None


class _FakeResult:
    def __init__(self, obj=None):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


class FakeSession:
    def __init__(self, query_result=None):
        self._query_result = query_result
        self._added = []
        self.commit_count = 0

    def add(self, obj):
        self._added.append(obj)
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
    with patch("backend.routers.review.posthog_capture"):
        yield


# ---------------------------------------------------------------------------
# POST /api/review/stream — validation errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_order_not_found_returns_404():
    """Non-existent order should return 404."""
    session = FakeSession(query_result=None)
    app.dependency_overrides[get_db] = _override_db(session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/review/stream",
                json={"order_id": str(uuid.uuid4())},
            )
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_review_unpaid_order_returns_402():
    """Unpaid order should return 402 Payment Required."""
    order = FakeOrder(payment_status="pending")
    session = FakeSession(query_result=order)
    app.dependency_overrides[get_db] = _override_db(session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/review/stream",
                json={"order_id": str(order.id)},
            )
        assert resp.status_code == 402
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_review_already_processing_returns_409():
    """Order already in processing state should return 409 Conflict."""
    order = FakeOrder(payment_status="paid", analysis_status="processing")
    session = FakeSession(query_result=order)
    app.dependency_overrides[get_db] = _override_db(session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/review/stream",
                json={"order_id": str(order.id)},
            )
        assert resp.status_code == 409
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_review_missing_contract_text_returns_422():
    """Order with no contract text and no staged upload should return 422."""
    order = FakeOrder(
        payment_status="paid",
        analysis_status="waiting",
        contract_text=None,
        temp_upload_token=None,
    )
    session = FakeSession(query_result=order)
    app.dependency_overrides[get_db] = _override_db(session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/review/stream",
                json={"order_id": str(order.id)},
            )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_review_missing_order_id_returns_422():
    """Request body without order_id should return 422."""
    session = FakeSession()
    app.dependency_overrides[get_db] = _override_db(session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/review/stream", json={})
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# POST /api/review/stream — SSE happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_stream_happy_path_returns_sse():
    """Paid order with contract text should start SSE streaming."""
    order = FakeOrder(
        payment_status="paid",
        analysis_status="waiting",
        contract_text="第1条 テスト契約",
    )
    session = FakeSession(query_result=order)
    app.dependency_overrides[get_db] = _override_db(session)

    # Mock the agent to yield a single complete event
    async def fake_stream(contract_text, target_language="ja"):
        yield {
            "type": "complete",
            "report": {
                "overall_risk_level": "低",
                "summary": "リスクは低いです。",
                "clause_analyses": [],
                "high_risk_count": 0,
                "medium_risk_count": 0,
                "low_risk_count": 1,
                "total_clauses": 1,
            },
        }

    try:
        with (
            patch("backend.routers.review.run_review_stream", side_effect=fake_stream),
            patch("backend.routers.review.cache_report", new_callable=AsyncMock),
            patch("backend.routers.review.send_report_email", new_callable=AsyncMock, return_value=True),
            patch("backend.routers.review.set_cost_order_context", return_value=None),
            patch("backend.routers.review.reset_cost_order_context"),
            patch("backend.routers.review.get_order_cost_summary", return_value=None),
            patch("backend.routers.review.clear_order_cost_summary"),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/review/stream",
                    json={"order_id": str(order.id)},
                )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        # Parse SSE lines
        lines = resp.text.strip().split("\n")
        data_lines = [ln for ln in lines if ln.startswith("data: ")]
        assert len(data_lines) >= 1
        first_event = json.loads(data_lines[0].replace("data: ", ""))
        assert first_event["type"] == "complete"
        assert first_event["report"]["overall_risk_level"] == "低"
    finally:
        app.dependency_overrides.pop(get_db, None)
