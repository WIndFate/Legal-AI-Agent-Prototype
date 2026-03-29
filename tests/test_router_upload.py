"""Integration tests for POST /api/upload endpoint."""

import io
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from backend.routers.upload import router
from backend.services.local_ocr import LocalOcrEstimate

app = FastAPI()
app.include_router(router)


@pytest.fixture(autouse=True)
def _mock_analytics():
    """Suppress PostHog calls during tests."""
    with patch("backend.routers.upload.posthog_capture"):
        yield


@pytest.fixture(autouse=True)
def _mock_clause_preview():
    """Avoid real LLM preview extraction in upload tests unless a case overrides it."""
    with patch("backend.routers.upload._extract_clause_preview", return_value=(None, None, None)):
        yield


@pytest.fixture(autouse=True)
def _mock_quote_guard():
    with (
        patch("backend.routers.upload.get_redis", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.upload.enforce_upload_rate_limit", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.upload.allow_preview_generation", new_callable=AsyncMock, return_value=True),
        patch("backend.routers.upload.load_cached_quote", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.upload.store_cached_quote", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.upload.build_quote_token", return_value="quote-test-token"),
    ):
        yield


@pytest.fixture(autouse=True)
def _clear_pricing_policy_cache():
    """Clear the lru_cache on get_pricing_policy so tests don't leak state."""
    from backend.services.token_estimator import get_pricing_policy
    get_pricing_policy.cache_clear()
    yield
    get_pricing_policy.cache_clear()


# -- Text upload happy path --------------------------------------------------


@pytest.mark.asyncio
async def test_upload_text_returns_pricing():
    """Text upload should return token estimate, pricing, and exact quote mode."""
    with patch(
        "backend.routers.upload._extract_clause_preview",
        return_value=([{"number": "第1条", "title": "目的"}], 1, {"preview_succeeded": True}),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/upload",
                data={
                    "input_type": "text",
                    "text": "第1条（目的）本契約は業務委託について定める。第2条 委託料は月額10万円とする。",
                },
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["quote_mode"] == "exact"
    assert body["estimate_source"] == "raw_text"
    assert body["ocr_required"] is False
    assert body["estimated_tokens"] > 0
    assert body["price_jpy"] > 0
    # Contract text should be echoed back for exact-mode quotes
    assert body["contract_text"] != ""
    assert body["clause_count"] == 1
    assert body["clause_preview"][0]["number"] == "第1条"
    assert body["quote_token"] == "quote-test-token"


@pytest.mark.asyncio
async def test_upload_empty_text_returns_zero_price():
    """Empty text input should return zero-price response."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/upload",
            data={"input_type": "text", "text": ""},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["price_jpy"] == 0
    assert body["estimated_tokens"] == 0


@pytest.mark.asyncio
async def test_upload_text_no_text_field_returns_zero():
    """POST with input_type=text but no text should return zero-price."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/upload",
            data={"input_type": "text"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["price_jpy"] == 0


# -- Text upload with PII detection -----------------------------------------


@pytest.mark.asyncio
async def test_upload_text_detects_pii():
    """Contract text with phone numbers should trigger PII warnings."""
    transport = ASGITransport(app=app)
    text_with_phone = "第1条 連絡先は090-1234-5678です。"
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/upload",
            data={"input_type": "text", "text": text_with_phone},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["pii_warnings"]) > 0
    assert any(w["type"] == "phone" for w in body["pii_warnings"])


# -- Image upload path (mocked staging) --------------------------------------


@pytest.mark.asyncio
async def test_upload_image_stages_file_and_requires_ocr():
    """Image upload should stage the file and return ocr_required=True."""
    fake_image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    with (
        patch("backend.routers.upload.stage_temp_upload", return_value="tok-abc123"),
        patch(
            "backend.routers.upload.estimate_text_with_local_ocr",
            return_value=LocalOcrEstimate(text="", provider="disabled"),
        ),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/upload",
                data={"input_type": "image"},
                files={"file": ("contract.png", io.BytesIO(fake_image_bytes), "image/png")},
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ocr_required"] is True
    assert body["ocr_confidence"] is None
    assert body["ocr_warnings"] == ["upload.ocr_post_payment_notice"]
    assert body["quote_mode"] == "estimated_pre_ocr"
    assert body["upload_token"] == "tok-abc123"


# -- PDF text-layer extraction path ------------------------------------------


@pytest.mark.asyncio
async def test_upload_pdf_with_text_layer_uses_exact_quote():
    """PDF with sufficient text layer should use exact quote mode."""
    fake_pdf = b"%PDF-1.4 fake content"
    extracted_text = "第1条 テスト契約" * 50  # enough text
    page_count = 2

    with (
        patch(
            "backend.routers.upload.extract_text_from_pdf_text_layer",
            return_value=(extracted_text, page_count),
        ),
        patch(
            "backend.routers.upload.pdf_text_layer_is_sufficient",
            return_value=True,
        ),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/upload",
                data={"input_type": "pdf"},
                files={"file": ("contract.pdf", io.BytesIO(fake_pdf), "application/pdf")},
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["quote_mode"] == "exact"
    assert body["estimate_source"] == "pdf_text_layer"
    assert body["ocr_required"] is False
    assert body["estimated_tokens"] > 0
    assert body["quote_token"] == "quote-test-token"


@pytest.mark.asyncio
async def test_upload_pdf_scanned_stages_for_ocr():
    """Scanned PDF without text layer should stage for OCR."""
    fake_pdf = b"%PDF-1.4 scanned"
    page_count = 3

    with (
        patch(
            "backend.routers.upload.extract_text_from_pdf_text_layer",
            return_value=("", page_count),
        ),
        patch(
            "backend.routers.upload.pdf_text_layer_is_sufficient",
            return_value=False,
        ),
        patch("backend.routers.upload.stage_temp_upload", return_value="tok-pdf456"),
        patch(
            "backend.routers.upload.estimate_text_with_local_ocr",
            return_value=LocalOcrEstimate(text="", provider="disabled"),
        ),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/upload",
                data={"input_type": "pdf"},
                files={"file": ("scan.pdf", io.BytesIO(fake_pdf), "application/pdf")},
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ocr_required"] is True
    assert body["ocr_confidence"] is None
    assert body["ocr_warnings"] == ["upload.ocr_post_payment_notice"]
    assert body["quote_mode"] == "estimated_pre_ocr"
    assert body["upload_token"] == "tok-pdf456"
    assert body["quote_token"] is None


@pytest.mark.asyncio
async def test_upload_image_with_low_quality_local_ocr_returns_warning():
    """Low-density OCR text should surface a low-confidence warning."""
    fake_image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    with (
        patch("backend.routers.upload.stage_temp_upload", return_value="tok-lowocr"),
        patch(
            "backend.routers.upload.estimate_text_with_local_ocr",
            return_value=LocalOcrEstimate(text="abc 123", provider="paddleocr"),
        ),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/upload",
                data={"input_type": "image"},
                files={"file": ("contract.png", io.BytesIO(fake_image_bytes), "image/png")},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ocr_confidence"] == "low"
    assert body["ocr_warnings"] == ["upload.ocr_low_quality"]


@pytest.mark.asyncio
async def test_upload_image_keeps_clause_preview_unavailable():
    """Image uploads should not return a clause preview before formal OCR."""
    fake_image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    with (
        patch("backend.routers.upload.stage_temp_upload", return_value="tok-imagepreview"),
        patch(
            "backend.routers.upload.estimate_text_with_local_ocr",
            return_value=LocalOcrEstimate(text="", provider="disabled"),
        ),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/upload",
                data={"input_type": "image"},
                files={"file": ("contract.png", io.BytesIO(fake_image_bytes), "image/png")},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["clause_preview"] is None
    assert body["clause_count"] is None
    assert body["quote_token"] is None


@pytest.mark.asyncio
async def test_upload_short_text_skips_clause_preview():
    """Very short exact-text uploads should not trigger preview extraction."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/upload",
            data={"input_type": "text", "text": "第1条 テスト契約"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["clause_preview"] is None
    assert body["clause_count"] is None


@pytest.mark.asyncio
async def test_upload_text_preview_failure_does_not_block_pricing():
    """Preview extraction failures should gracefully degrade to null preview."""
    with patch("backend.routers.upload._extract_clause_preview", return_value=(None, None, None)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/upload",
                data={
                    "input_type": "text",
                    "text": "第1条（目的）本契約は業務委託について定める。第2条 委託料は月額10万円とする。第3条 契約期間は1年とする。",
                },
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["price_jpy"] > 0
    assert body["clause_preview"] is None
    assert body["clause_count"] is None


# -- Upload limit enforcement ------------------------------------------------


@pytest.mark.asyncio
async def test_upload_text_exceeding_max_tokens_returns_413():
    """Contract text exceeding MAX_CONTRACT_TOKENS should be rejected."""
    # Create text that will exceed the token limit
    huge_text = "第1条 " * 100000

    with patch("backend.routers.upload.get_settings") as mock_settings:
        settings = mock_settings.return_value
        settings.MAX_UPLOAD_PAGES = 30
        settings.MAX_CONTRACT_TOKENS = 100  # very low limit for testing
        settings.ENABLE_LOCAL_OCR_ESTIMATE = False
        settings.PRICING_POLICY_FILE = "backend/data/pricing_policy.json"

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/upload",
                data={"input_type": "text", "text": huge_text},
            )
    assert resp.status_code == 413
