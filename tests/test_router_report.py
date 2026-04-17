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
ACCESS_TOKEN = "access-token-123"
SHARE_TOKEN = "share-token-123"
OWNER_HEADERS = {"X-Order-Token": ACCESS_TOKEN}


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
    session.get = AsyncMock()
    app.dependency_overrides.clear()

    async def _override():
        yield session

    from backend.db.session import get_db
    app.dependency_overrides[get_db] = _override
    yield session
    app.dependency_overrides.clear()


def _db_result(report_row):
    report_result = MagicMock()
    report_result.scalar_one_or_none.return_value = report_row
    return report_result


def _mock_order(order_id: uuid.UUID, share_token: str | None = SHARE_TOKEN):
    order = MagicMock()
    order.id = order_id
    order.access_token = ACCESS_TOKEN
    order.share_token = share_token
    return order


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
    mock_db.get.return_value = _mock_order(uuid.UUID(oid))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/report/{oid}", headers=OWNER_HEADERS)

    assert resp.status_code == 200
    assert resp.json()["report"]["summary"] == "キャッシュ要約"


@pytest.mark.asyncio
@patch("backend.routers.report.posthog_capture")
@patch("backend.routers.report.get_cached_report")
async def test_report_allows_share_token(mock_cache, mock_posthog, mock_db):
    oid = str(uuid.uuid4())
    cached_payload = {
        "order_id": oid,
        "report": {
            "overall_risk_level": "低",
            "summary": "共有リンク要約",
            "clause_analyses": [],
            "high_risk_count": 0,
            "medium_risk_count": 0,
            "low_risk_count": 0,
            "total_clauses": 0,
        },
        "language": "ja",
    }
    mock_cache.return_value = cached_payload
    mock_db.get.return_value = _mock_order(uuid.UUID(oid))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/report/{oid}?s={SHARE_TOKEN}")

    assert resp.status_code == 200
    assert resp.json()["report"]["summary"] == "共有リンク要約"


@pytest.mark.asyncio
@patch("backend.routers.report.posthog_capture")
@patch("backend.routers.report.get_cached_report", return_value=None)
async def test_report_rejects_owner_token_in_share_query(mock_cache, mock_posthog, mock_db):
    """Owner access token must not unlock the share path — that path only
    accepts the dedicated share_token."""
    oid = uuid.uuid4()
    mock_db.get.return_value = _mock_order(oid)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/report/{oid}?s={ACCESS_TOKEN}")

    assert resp.status_code == 404


# ── Redis cache miss → DB hit ────────────────────────────────────

@pytest.mark.asyncio
@patch("backend.routers.report.posthog_capture")
@patch("backend.routers.report.get_cached_report", return_value=None)
async def test_report_cache_miss_db_hit(mock_cache, mock_posthog, mock_db):
    oid = uuid.uuid4()
    report_row = _make_report_row(oid)
    mock_db.get.return_value = _mock_order(oid)
    mock_db.execute.return_value = _db_result(report_row)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/report/{oid}", headers=OWNER_HEADERS)

    assert resp.status_code == 200
    body = resp.json()
    assert body["order_id"] == str(oid)
    assert body["report"]["overall_risk_level"] == "中"
    assert body["language"] == "zh-CN"


@pytest.mark.asyncio
@patch("backend.routers.report.posthog_capture")
@patch("backend.routers.report.get_cached_report", return_value=None)
async def test_report_clause_order_is_sorted_by_risk(mock_cache, mock_posthog, mock_db):
    oid = uuid.uuid4()
    report_row = _make_report_row(oid)
    report_row.clause_analyses = [
        {"clause_number": "第3条", "risk_level": "低"},
        {"clause_number": "第1条", "risk_level": "高"},
        {"clause_number": "第2条", "risk_level": "中"},
    ]
    mock_db.get.return_value = _mock_order(oid)
    mock_db.execute.return_value = _db_result(report_row)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/report/{oid}", headers=OWNER_HEADERS)

    assert resp.status_code == 200
    clause_numbers = [item["clause_number"] for item in resp.json()["report"]["clause_analyses"]]
    assert clause_numbers == ["第1条", "第2条", "第3条"]


# ── Report not found → 404 ──────────────────────────────────────

@pytest.mark.asyncio
@patch("backend.routers.report.posthog_capture")
@patch("backend.routers.report.get_cached_report", return_value=None)
async def test_report_not_found(mock_cache, mock_posthog, mock_db):
    oid = uuid.uuid4()
    mock_db.get.return_value = _mock_order(oid)
    mock_db.execute.return_value = _db_result(None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/report/{oid}", headers=OWNER_HEADERS)

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ── Expired report → 404 ────────────────────────────────────────

@pytest.mark.asyncio
@patch("backend.routers.report.posthog_capture")
@patch("backend.routers.report.get_cached_report", return_value=None)
async def test_report_expired(mock_cache, mock_posthog, mock_db):
    oid = uuid.uuid4()
    report_row = _make_report_row(oid, expired=True)
    mock_db.get.return_value = _mock_order(oid)
    mock_db.execute.return_value = _db_result(report_row)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/report/{oid}", headers=OWNER_HEADERS)

    assert resp.status_code == 404
    assert "expired" in resp.json()["detail"].lower()


@pytest.mark.asyncio
@patch("backend.routers.report.posthog_capture")
@patch("backend.routers.report.report_pdf_renderer.build_pdf", return_value=b"%PDF-1.4 test")
async def test_report_pdf_download(mock_renderer, mock_posthog, mock_db):
    oid = uuid.uuid4()
    report_row = _make_report_row(oid)
    mock_db.get.return_value = _mock_order(oid)
    mock_db.execute.return_value = _db_result(report_row)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/report/{oid}/pdf", headers=OWNER_HEADERS)

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/octet-stream")
    assert f'contractguard-report-{oid}.pdf' in resp.headers["content-disposition"]
    assert "attachment;" in resp.headers["content-disposition"]
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.content.startswith(b"%PDF-1.4")


@pytest.mark.asyncio
@patch("backend.routers.report.posthog_capture")
@patch("backend.routers.report.report_pdf_renderer.build_pdf", return_value=b"%PDF-1.4 test")
async def test_report_pdf_download_with_share_token(mock_renderer, mock_posthog, mock_db):
    oid = uuid.uuid4()
    report_row = _make_report_row(oid)
    mock_db.get.return_value = _mock_order(oid)
    mock_db.execute.return_value = _db_result(report_row)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/report/{oid}/pdf?s={SHARE_TOKEN}")

    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF-1.4")


@pytest.mark.asyncio
@patch("backend.routers.report.posthog_capture")
@patch("backend.routers.report.get_cached_report", return_value=None)
async def test_report_rejects_missing_token(mock_cache, mock_posthog, mock_db):
    oid = uuid.uuid4()
    report_row = _make_report_row(oid)
    mock_db.get.return_value = _mock_order(oid)
    mock_db.execute.return_value = _db_result(report_row)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/report/{oid}")

    assert resp.status_code == 404


@pytest.mark.asyncio
@patch("backend.routers.report.posthog_capture")
@patch("backend.routers.report.get_cached_report", return_value=None)
async def test_report_rejects_query_token_owner_path(mock_cache, mock_posthog, mock_db):
    """Legacy `?token=` on the URL must not authorize the owner path — owner
    access only via X-Order-Token header."""
    oid = uuid.uuid4()
    report_row = _make_report_row(oid)
    mock_db.get.return_value = _mock_order(oid)
    mock_db.execute.return_value = _db_result(report_row)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/report/{oid}?token={ACCESS_TOKEN}")

    assert resp.status_code == 404


@pytest.mark.asyncio
@patch("backend.routers.report.build_order_share_token", return_value="freshly-minted-share-token")
async def test_report_share_link_mints_fresh_token(mock_build, mock_db):
    oid = uuid.uuid4()
    order = MagicMock()
    order.id = oid
    order.access_token = ACCESS_TOKEN
    order.share_token = None  # no token yet
    mock_db.get = AsyncMock(return_value=order)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/report/{oid}/share-link", headers=OWNER_HEADERS
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["order_id"] == str(oid)
    assert body["share_token"] == "freshly-minted-share-token"
    # Persisted onto the order.
    assert order.share_token == "freshly-minted-share-token"
    mock_db.commit.assert_awaited()


@pytest.mark.asyncio
@patch("backend.routers.report.build_order_share_token", return_value="should-not-be-called")
async def test_report_share_link_is_stable(mock_build, mock_db):
    """Calling /share-link twice must return the same token (no re-mint)."""
    oid = uuid.uuid4()
    existing_share_token = "preexisting-share-token"
    order = MagicMock()
    order.id = oid
    order.access_token = ACCESS_TOKEN
    order.share_token = existing_share_token
    mock_db.get = AsyncMock(return_value=order)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/report/{oid}/share-link", headers=OWNER_HEADERS
        )

    assert resp.status_code == 200
    assert resp.json()["share_token"] == existing_share_token
    # Pre-existing token preserved — generator must not fire.
    mock_build.assert_not_called()
    assert order.share_token == existing_share_token


@pytest.mark.asyncio
async def test_report_share_link_rejects_share_token_in_header(mock_db):
    """Share-token holder must not be able to mint a share link; only the
    owner's access_token via X-Order-Token unlocks this endpoint."""
    oid = uuid.uuid4()
    mock_db.get = AsyncMock(return_value=_mock_order(oid))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/report/{oid}/share-link",
            headers={"X-Order-Token": SHARE_TOKEN},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_report_share_link_rejects_missing_header(mock_db):
    oid = uuid.uuid4()
    mock_db.get = AsyncMock(return_value=_mock_order(oid))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(f"/api/report/{oid}/share-link")

    assert resp.status_code == 404


# ── DELETE /share-link revocation ───────────────────────────────

@pytest.mark.asyncio
async def test_report_share_link_revoke_clears_token(mock_db):
    oid = uuid.uuid4()
    order = MagicMock()
    order.id = oid
    order.access_token = ACCESS_TOKEN
    order.share_token = SHARE_TOKEN
    mock_db.get = AsyncMock(return_value=order)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete(
            f"/api/report/{oid}/share-link", headers=OWNER_HEADERS
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["order_id"] == str(oid)
    assert body["revoked"] is True
    assert order.share_token is None
    mock_db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_report_share_link_revoke_idempotent_when_none(mock_db):
    """Revoking when no share token exists must return revoked=False without
    committing — avoids a write on every idempotent call."""
    oid = uuid.uuid4()
    order = MagicMock()
    order.id = oid
    order.access_token = ACCESS_TOKEN
    order.share_token = None
    mock_db.get = AsyncMock(return_value=order)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete(
            f"/api/report/{oid}/share-link", headers=OWNER_HEADERS
        )

    assert resp.status_code == 200
    assert resp.json()["revoked"] is False
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_report_share_link_revoke_rejects_share_token_holder(mock_db):
    oid = uuid.uuid4()
    mock_db.get = AsyncMock(return_value=_mock_order(oid))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete(
            f"/api/report/{oid}/share-link",
            headers={"X-Order-Token": SHARE_TOKEN},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_report_share_link_revoke_rejects_missing_header(mock_db):
    oid = uuid.uuid4()
    mock_db.get = AsyncMock(return_value=_mock_order(oid))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete(f"/api/report/{oid}/share-link")

    assert resp.status_code == 404
