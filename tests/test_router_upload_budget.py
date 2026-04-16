from __future__ import annotations

import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.routers.upload import router

app = FastAPI()
app.include_router(router)


@pytest.fixture(autouse=True)
def _mock_common_dependencies():
    with (
        patch("backend.routers.upload.get_redis", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.upload.enforce_upload_rate_limit", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.upload.load_ocr_result_cache", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.upload.store_ocr_result_cache", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.upload.check_ocr_allowed", new_callable=AsyncMock, return_value=True),
        patch("backend.routers.upload.record_ocr_upload", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.upload.rollback_ocr_upload", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.upload.allow_preview_generation", new_callable=AsyncMock, return_value=False),
        patch("backend.routers.upload.load_cached_quote", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.upload.store_cached_quote", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.upload.build_quote_token", return_value="quote-token"),
        patch("backend.routers.upload.posthog_capture"),
        patch("backend.routers.upload.extract_text_from_image_with_snapshot", new_callable=AsyncMock, return_value=("第1条 テスト契約", {"ocr_model": "google-vision-document-text", "ocr_input_tokens": 1, "ocr_output_tokens": 20, "ocr_cost_jpy": 0.225, "ocr_cost_usd": 0.0015, "ocr_succeeded": True})),
    ):
        yield


@pytest.mark.asyncio
async def test_upload_returns_503_when_budget_rejects_image_ocr():
    fake_image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    with patch(
        "backend.routers.upload.check_budget_allowed",
        new_callable=AsyncMock,
        return_value=False,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/upload",
                data={"input_type": "image"},
                files={"file": ("contract.png", io.BytesIO(fake_image_bytes), "image/png")},
            )

    assert resp.status_code == 503
    assert resp.json()["detail"] == "daily_budget_exhausted"


@pytest.mark.asyncio
async def test_upload_succeeds_when_budget_allows_image_ocr():
    fake_image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    with patch(
        "backend.routers.upload.check_budget_allowed",
        new_callable=AsyncMock,
        return_value=True,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/upload",
                data={"input_type": "image"},
                files={"file": ("contract.png", io.BytesIO(fake_image_bytes), "image/png")},
            )

    assert resp.status_code == 200
    assert resp.json()["price_jpy"] > 0
