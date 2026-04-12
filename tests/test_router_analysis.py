"""Integration tests for persistent analysis task routes."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.db.session import get_db
from backend.models.analysis_event import AnalysisEvent
from backend.models.analysis_job import AnalysisJob
from backend.models.order import Order
from backend.models.report import Report
from backend.routers.analysis import router

app = FastAPI()
app.include_router(router)


class FakeOrder:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.payment_status = kwargs.get("payment_status", "paid")
        self.analysis_status = kwargs.get("analysis_status", "waiting")
        self.target_language = kwargs.get("target_language", "zh-CN")
        self.email = kwargs.get("email", "test@example.com")
        self.contract_text = kwargs.get("contract_text", "第1条 テスト契約")


class FakeJob:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.order_id = kwargs.get("order_id", uuid.uuid4())
        self.status = kwargs.get("status", "queued")
        self.current_step = kwargs.get("current_step")
        self.progress_message = kwargs.get("progress_message")
        self.progress_seq = kwargs.get("progress_seq", 0)
        self.cost_summary = kwargs.get("cost_summary")
        self.target_language = kwargs.get("target_language", "zh-CN")
        self.error_code = kwargs.get("error_code")
        self.error_message = kwargs.get("error_message")
        self.started_at = kwargs.get("started_at")
        self.finished_at = kwargs.get("finished_at")
        self.failed_at = kwargs.get("failed_at")
        self.last_event_at = kwargs.get("last_event_at")


class FakeEvent:
    def __init__(self, **kwargs):
        self.seq = kwargs.get("seq", 1)
        self.event_type = kwargs.get("event_type", "node_start")
        self.step = kwargs.get("step", "analyzing")
        self.message = kwargs.get("message", "Analyzing clauses")
        self.payload_json = kwargs.get("payload_json", {"type": "node_start", "node": "analyze_risks"})
        self.created_at = kwargs.get("created_at", datetime.now(timezone.utc))


class _ScalarResult:
    def __init__(self, obj=None):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


class _ListResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class FakeSession:
    def __init__(self, *, order=None, job=None, report_exists=False, events=None):
        self.order = order
        self.job = job
        self.report_exists = report_exists
        self.events = events or []
        self.added = []
        self.commit_count = 0

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, AnalysisJob):
            self.job = obj

    async def get(self, model, key):
        if model is Order:
            return self.order if self.order and str(self.order.id) == str(key) else None
        if model is AnalysisJob:
            return self.job if self.job and str(self.job.id) == str(key) else None
        return None

    async def commit(self):
        self.commit_count += 1

    async def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()

    async def execute(self, stmt):
        entity = stmt.column_descriptions[0].get("entity")
        if entity is AnalysisJob:
            return _ScalarResult(self.job)
        if entity is AnalysisEvent:
            return _ListResult(self.events)
        if entity is Report:
            return _ScalarResult(uuid.uuid4() if self.report_exists else None)
        return _ScalarResult(None)


def _override_db(session: FakeSession):
    async def _dep():
        yield session

    return _dep


@pytest.fixture(autouse=True)
def _mock_executor_helpers():
    with (
        patch("backend.routers.analysis.launch_analysis", new_callable=AsyncMock),
        patch("backend.routers.analysis.reset_failed_job", new_callable=AsyncMock),
        patch("backend.routers.analysis.is_analysis_running", return_value=False),
    ):
        yield


@pytest.mark.asyncio
async def test_start_analysis_creates_job_and_launches_executor():
    order = FakeOrder()
    session = FakeSession(order=order)
    app.dependency_overrides[get_db] = _override_db(session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/analysis/start", json={"order_id": str(order.id)})
        assert response.status_code == 200
        payload = response.json()
        assert payload["order_id"] == str(order.id)
        assert payload["status"] == "queued"
        assert session.job is not None
        assert session.commit_count == 1
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_start_analysis_unpaid_order_returns_402():
    order = FakeOrder(payment_status="pending")
    session = FakeSession(order=order)
    app.dependency_overrides[get_db] = _override_db(session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/analysis/start", json={"order_id": str(order.id)})
        assert response.status_code == 402
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_order_status_prefers_analysis_job_snapshot():
    order = FakeOrder(analysis_status="waiting")
    job = FakeJob(
        order_id=order.id,
        status="processing",
        current_step="analyzing",
        progress_message="正在分析条款",
        progress_seq=3,
        started_at=datetime.now(timezone.utc),
    )
    session = FakeSession(order=order, job=job, report_exists=True)
    app.dependency_overrides[get_db] = _override_db(session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/orders/{order.id}/status")
        assert response.status_code == 200
        payload = response.json()
        assert payload["analysis_status"] == "processing"
        assert payload["current_step"] == "analyzing"
        assert payload["progress_seq"] == 3
        assert payload["report_ready"] is True
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_get_analysis_events_returns_history():
    order = FakeOrder()
    job = FakeJob(order_id=order.id, status="processing")
    event = FakeEvent()
    session = FakeSession(order=order, job=job, events=[event])
    app.dependency_overrides[get_db] = _override_db(session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/orders/{order.id}/events?after_seq=0")
        assert response.status_code == 200
        payload = response.json()
        assert payload["order_id"] == str(order.id)
        assert len(payload["events"]) == 1
        assert payload["events"][0]["seq"] == 1
        assert payload["events"][0]["event_type"] == "node_start"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_order_status_rejects_non_uuid_order_id_as_404():
    # Non-UUID path parameters must return 404 instead of leaking a SQL DataError as 500.
    session = FakeSession()
    app.dependency_overrides[get_db] = _override_db(session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/orders/not-a-uuid/status")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_stream_analysis_events_replays_terminal_history_only():
    order = FakeOrder()
    job = FakeJob(order_id=order.id, status="completed")
    event = FakeEvent(event_type="complete", message="Analysis completed", payload_json={"type": "complete", "report_ready": True})
    session = FakeSession(order=order, job=job, events=[event])
    app.dependency_overrides[get_db] = _override_db(session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/orders/{order.id}/stream?after_seq=0")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        data_lines = [line for line in response.text.splitlines() if line.startswith("data: ")]
        assert len(data_lines) == 1
        payload = json.loads(data_lines[0].replace("data: ", ""))
        assert payload["event_type"] == "complete"
        assert payload["payload_json"]["report_ready"] is True
    finally:
        app.dependency_overrides.pop(get_db, None)
