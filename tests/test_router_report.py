"""Integration tests for GET /api/report/{order_id} endpoint."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.routers.report import router

app = FastAPI()
app.include_router(router)


def _make_report_row(
    order_id: uuid.UUID,
    expired: bool = False,
    language: str = "zh-CN",
):
    """Build a mock Report ORM object."""
    now = datetime.now(timezone.utc)
    row = MagicMock()
    row.order_id = order_id
    row.overall_risk_level = "中"
    row.summary = "テスト要約"
    row.clause_analyses = [{"clause_number": "第1条", "risk_level": "低"}]
    row.high_risk_count = 0
    row.medium_risk_count = 1
    row.low_risk_count = 1
    row.total_clauses = 2
    row.language = language
    row.created_at = now - timedelta(hours=1)
    row.expires_at = now - timedelta(hours=1) if expired else now + timedelta(hours=71)
    return row


@pytest.fixture
def mock_db():
    """Provide a mock AsyncSession and override the get_db dependency."""
    session = AsyncMock()
    app.dependency_overrides.clear()

    async def _override():
        yield session

    from backend.db.session import get_db
    app.dependency_overrides[get_db] = _override
    yield session
    app.dependency_overrides.clear()


# ── Redis cache hit ───────────────────────────────────────────────

@pytest.mark.asyncio
@patch("backend.routers.report.posthog_capture")
@patch("backend.routers.report.get_cached_report")
async def test_report_cache_hit(mock_cache, mock_posthog, mock_db):
    oid = str(uuid.uuid4())
    cached_payload = {
        "order_id": oid,
        "report": {
            "overall_risk_level": "低",
            "summary": "キャッシュ要約",
            "clause_analyses": [],
            "high_risk_count": 0,
            "medium_risk_count": 0,
            "low_risk_count": 0,
            "total_clauses": 0,
        },
        "language": "ja",
    }
    mock_cache.return_value = cached_payload

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/report/{oid}")

    assert resp.status_code == 200
    assert resp.json()["report"]["summary"] == "キャッシュ要約"


# ── Redis cache miss → DB hit ────────────────────────────────────

@pytest.mark.asyncio
@patch("backend.routers.report.posthog_capture")
@patch("backend.routers.report.get_cached_report", return_value=None)
async def test_report_cache_miss_db_hit(mock_cache, mock_posthog, mock_db):
    oid = uuid.uuid4()
    report_row = _make_report_row(oid)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = report_row
    mock_db.execute.return_value = result_mock

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/report/{oid}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["order_id"] == str(oid)
    assert body["report"]["overall_risk_level"] == "中"
    assert body["language"] == "zh-CN"


# ── Report not found → 404 ──────────────────────────────────────

@pytest.mark.asyncio
@patch("backend.routers.report.posthog_capture")
@patch("backend.routers.report.get_cached_report", return_value=None)
async def test_report_not_found(mock_cache, mock_posthog, mock_db):
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = result_mock

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/report/{uuid.uuid4()}")

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ── Expired report → 404 ────────────────────────────────────────

@pytest.mark.asyncio
@patch("backend.routers.report.posthog_capture")
@patch("backend.routers.report.get_cached_report", return_value=None)
async def test_report_expired(mock_cache, mock_posthog, mock_db):
    oid = uuid.uuid4()
    report_row = _make_report_row(oid, expired=True)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = report_row
    mock_db.execute.return_value = result_mock

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/report/{oid}")

    assert resp.status_code == 404
    assert "expired" in resp.json()["detail"].lower()


@pytest.mark.asyncio
@patch("backend.routers.report.posthog_capture")
@patch("backend.routers.report.report_pdf_renderer.build_pdf", return_value=b"%PDF-1.4 test")
async def test_report_pdf_download(mock_renderer, mock_posthog, mock_db):
    oid = uuid.uuid4()
    report_row = _make_report_row(oid)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = report_row
    mock_db.execute.return_value = result_mock

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/report/{oid}/pdf")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert f'contractguard-report-{oid}.pdf' in resp.headers["content-disposition"]
    assert resp.content.startswith(b"%PDF-1.4")
