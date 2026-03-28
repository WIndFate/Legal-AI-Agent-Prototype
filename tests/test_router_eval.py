"""Integration tests for /api/eval/* endpoints."""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.routers.eval import router

app = FastAPI()
app.include_router(router)


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


# ── GET /api/eval/rag ────────────────────────────────────────────

@pytest.mark.asyncio
@patch("backend.routers.eval.run_rag_eval")
async def test_eval_rag_default_k(mock_eval):
    mock_eval.return_value = {
        "k": 3,
        "num_queries": 20,
        "mean_recall_at_k": 0.54,
        "mrr": 0.82,
        "per_query": [],
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/eval/rag")

    assert resp.status_code == 200
    body = resp.json()
    assert body["k"] == 3
    assert body["mean_recall_at_k"] == 0.54
    mock_eval.assert_called_once_with(k=3)


@pytest.mark.asyncio
@patch("backend.routers.eval.run_rag_eval")
async def test_eval_rag_custom_k(mock_eval):
    mock_eval.return_value = {
        "k": 10,
        "num_queries": 20,
        "mean_recall_at_k": 0.72,
        "mrr": 0.85,
        "per_query": [],
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/eval/rag?k=10")

    assert resp.status_code == 200
    assert resp.json()["k"] == 10
    mock_eval.assert_called_once_with(k=10)


# ── GET /api/eval/costs ──────────────────────────────────────────

@pytest.mark.asyncio
@patch("backend.routers.eval.build_cost_pricing_report")
@patch("backend.routers.eval.summarize_sample_sources")
@patch("backend.routers.eval.load_cost_samples")
async def test_eval_costs_default_params(mock_load, mock_sources, mock_report, mock_db):
    mock_load.return_value = [
        {"source": "seed", "total_cost_usd": 0.05},
        {"source": "seed", "total_cost_usd": 0.08},
    ]
    mock_sources.return_value = {"seed": 2, "db": 0}
    mock_report.return_value = {"mean_cost_usd": 0.065}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/eval/costs")

    assert resp.status_code == 200
    body = resp.json()
    assert body["samples"] == 2
    assert body["sample_sources"] == {"seed": 2, "db": 0}
    assert body["report"]["mean_cost_usd"] == 0.065


@pytest.mark.asyncio
async def test_eval_costs_invalid_rates(mock_db):
    """payment_fee_rate + target_margin_rate >= 1.0 should return 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/eval/costs?payment_fee_rate=0.5&target_margin_rate=0.6"
        )

    assert resp.status_code == 422
    assert "must be < 1.0" in resp.json()["detail"]


@pytest.mark.asyncio
@patch("backend.routers.eval.build_cost_pricing_report")
@patch("backend.routers.eval.summarize_sample_sources")
@patch("backend.routers.eval.load_cost_samples")
async def test_eval_costs_custom_params(mock_load, mock_sources, mock_report, mock_db):
    mock_load.return_value = []
    mock_sources.return_value = {"seed": 0, "db": 0}
    mock_report.return_value = {}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/eval/costs?limit=50&safety_multiplier=3.0"
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["sample_limit"] == 50
    # Verify custom params passed through
    mock_report.assert_called_once()
    call_kwargs = mock_report.call_args
    assert call_kwargs[1]["safety_multiplier"] == 3.0


@pytest.mark.asyncio
@patch("backend.routers.eval.build_ops_dashboard")
@patch("backend.routers.eval.summarize_sample_sources")
@patch("backend.routers.eval.load_cost_samples")
async def test_eval_operations_dashboard(mock_load, mock_sources, mock_dashboard, mock_db):
    mock_load.return_value = [
        {"order_id": "a", "paid_price_jpy": 799, "total_cost_jpy": 23.1},
    ]
    mock_sources.return_value = {"database_samples": 1, "seed_samples": 0}
    mock_dashboard.return_value = {"overall": {"actual_margin_jpy": {"avg": 775.9}}}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/eval/operations?limit=50&recent_limit=10")

    assert resp.status_code == 200
    body = resp.json()
    assert body["sample_limit"] == 50
    assert body["recent_limit"] == 10
    assert body["samples"] == 1
    assert body["sample_sources"] == {"database_samples": 1, "seed_samples": 0}
    assert body["dashboard"]["overall"]["actual_margin_jpy"]["avg"] == 775.9
    mock_load.assert_called_once_with(mock_db, limit=50, include_seed=False)
    mock_dashboard.assert_called_once_with(mock_load.return_value, recent_limit=10)
