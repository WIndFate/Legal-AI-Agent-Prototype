"""Integration tests for GET /api/health endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.routers.health import router

from fastapi import FastAPI

app = FastAPI()
app.include_router(router)


@pytest.mark.asyncio
async def test_health_returns_ok():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_wrong_method_returns_405():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/health")
    assert resp.status_code == 405
