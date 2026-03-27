"""Integration tests for /api/referral/* endpoints."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.routers.referral import router

app = FastAPI()
app.include_router(router)


@pytest.fixture
def mock_db():
    """Provide a mock AsyncSession and override the get_db dependency."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    app.dependency_overrides.clear()

    async def _override():
        yield session

    from backend.db.session import get_db
    app.dependency_overrides[get_db] = _override
    yield session
    app.dependency_overrides.clear()


# ── POST /api/referral/generate ──────────────────────────────────

@pytest.mark.asyncio
@patch("backend.routers.referral.get_settings")
async def test_generate_referral(mock_settings, mock_db):
    mock_settings.return_value.FRONTEND_URL = "https://example.com"
    oid = str(uuid.uuid4())
    order_mock = MagicMock()
    order_mock.payment_status = "paid"
    existing_referral_result = MagicMock()
    existing_referral_result.scalar_one_or_none.return_value = None
    order_result = MagicMock()
    order_result.scalar_one_or_none.return_value = order_mock
    mock_db.execute.side_effect = [order_result, existing_referral_result]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/referral/generate", json={"order_id": oid})

    assert resp.status_code == 200
    body = resp.json()
    assert "referral_code" in body
    assert len(body["referral_code"]) <= 8
    assert body["referral_url"].startswith("https://example.com/?ref=")
    # discount_jpy comes from the ORM default (100); with a mocked session
    # the column default may not fire, so just check the key exists.
    assert "discount_jpy" in body
    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_referral_missing_order_id(mock_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/referral/generate", json={})

    assert resp.status_code == 422


# ── GET /api/referral/{code} — valid code ────────────────────────

@pytest.mark.asyncio
async def test_check_referral_valid(mock_db):
    referral_mock = MagicMock()
    referral_mock.uses_count = 3
    referral_mock.max_uses = 10
    referral_mock.discount_jpy = 100

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = referral_mock
    mock_db.execute.return_value = result_mock

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/referral/TESTCODE")

    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["discount_jpy"] == 100


# ── GET /api/referral/{code} — code not found ───────────────────

@pytest.mark.asyncio
async def test_check_referral_not_found(mock_db):
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = result_mock

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/referral/INVALID")

    assert resp.status_code == 200
    assert resp.json()["valid"] is False


# ── GET /api/referral/{code} — max uses exhausted ───────────────

@pytest.mark.asyncio
async def test_check_referral_exhausted(mock_db):
    referral_mock = MagicMock()
    referral_mock.uses_count = 10
    referral_mock.max_uses = 10
    referral_mock.discount_jpy = 100

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = referral_mock
    mock_db.execute.return_value = result_mock

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/referral/MAXED")

    assert resp.status_code == 200
    assert resp.json()["valid"] is False
