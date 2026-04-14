"""Integration tests for POST /api/upload endpoint."""

import io
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from backend.routers.upload import router

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
    with patch("backend.routers.upload._extract_clause_preview", return_value=(None, None, None, None)):
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
        return_value=([{"number": "第1条", "title": "目的"}], 1, {"preview_succeeded": True}, True),
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
    assert body["estimated_tokens"] > 0
    assert body["price_jpy"] > 0
    # Contract text should be echoed back for exact-mode quotes
    assert body["contract_text"] != ""
    assert body["clause_count"] == 1
    assert body["clause_preview"][0]["number"] == "第1条"
    assert body["is_contract"] is True
    assert body["quote_token"] == "quote-test-token"


@pytest.mark.asyncio
async def test_upload_text_non_contract_sets_is_contract_false():
    """Exact quote uploads should surface non-contract detection before payment."""
    with patch(
        "backend.routers.upload._extract_clause_preview",
        return_value=(None, None, {"preview_succeeded": True}, False),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/upload",
                data={
                    "input_type": "text",
                    "text": "これは会議メモです。契約条件や当事者間の合意条項は含まれていません。",
                },
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["price_jpy"] > 0
    assert body["is_contract"] is False


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


# -- Image upload path (Vision OCR) -----------------------------------------


@pytest.mark.asyncio
async def test_upload_image_uses_vision_ocr_and_returns_exact_quote():
    """Image upload should use Vision OCR to extract text and return exact quote."""
    fake_image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    ocr_text = "第1条（目的）本契約は業務委託について定める。第2条 委託料は月額10万円とする。"

    with (
        patch(
            "backend.routers.upload.extract_text_from_image_with_snapshot",
            new_callable=AsyncMock,
            return_value=(
                ocr_text,
                {"ocr_model": "gpt-4o", "ocr_input_tokens": 1200, "ocr_output_tokens": 400, "ocr_cost_jpy": 0.75, "ocr_cost_usd": 0.005, "ocr_succeeded": True},
            ),
        ),
        patch(
            "backend.routers.upload._extract_clause_preview",
            return_value=([{"number": "第1条", "title": "目的"}], 1, {"preview_succeeded": True}, True),
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
    assert body["quote_mode"] == "exact"
    assert body["estimate_source"] == "vision_ocr"
    assert body["estimated_tokens"] > 0
    assert body["price_jpy"] > 0
    assert body["contract_text"] == ocr_text
    assert body["is_contract"] is True
    assert body["clause_preview"][0]["number"] == "第1条"
    assert body["quote_token"] == "quote-test-token"


@pytest.mark.asyncio
async def test_upload_image_non_contract_sets_is_contract_false():
    """Non-contract images should be detected before payment."""
    fake_image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    with (
        patch(
            "backend.routers.upload.extract_text_from_image_with_snapshot",
            new_callable=AsyncMock,
            return_value=(
                "これは会議メモです。契約条件は含まれていません。",
                {"ocr_model": "gpt-4o", "ocr_input_tokens": 900, "ocr_output_tokens": 120, "ocr_cost_jpy": 0.42, "ocr_cost_usd": 0.0028, "ocr_succeeded": True},
            ),
        ),
        patch(
            "backend.routers.upload._extract_clause_preview",
            return_value=(None, None, {"preview_succeeded": True}, False),
        ),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/upload",
                data={"input_type": "image"},
                files={"file": ("memo.png", io.BytesIO(fake_image_bytes), "image/png")},
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["quote_mode"] == "exact"
    assert body["is_contract"] is False
    assert body["price_jpy"] > 0


@pytest.mark.asyncio
async def test_upload_image_empty_ocr_returns_zero_price():
    """Image that yields no OCR text should return zero-price response."""
    fake_image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    with patch(
        "backend.routers.upload.extract_text_from_image_with_snapshot",
        new_callable=AsyncMock,
        return_value=("", {"ocr_model": "gpt-4o", "ocr_input_tokens": 500, "ocr_output_tokens": 0, "ocr_cost_jpy": 0.15, "ocr_cost_usd": 0.001, "ocr_succeeded": True}),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/upload",
                data={"input_type": "image"},
                files={"file": ("blank.png", io.BytesIO(fake_image_bytes), "image/png")},
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["price_jpy"] == 0
    assert body["estimated_tokens"] == 0


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
    assert body["estimated_tokens"] > 0
    assert body["quote_token"] == "quote-test-token"


@pytest.mark.asyncio
async def test_upload_scanned_pdf_uses_vision_ocr():
    """Scanned PDF without text layer should use Vision OCR and return exact quote."""
    fake_pdf = b"%PDF-1.4 scanned"
    ocr_text = "第1条 テスト契約 第2条 契約期間は1年とする。"
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
        patch(
            "backend.routers.upload.extract_text_from_pdf_with_snapshot",
            new_callable=AsyncMock,
            return_value=(
                ocr_text,
                {"ocr_model": "gpt-4o", "ocr_input_tokens": 1800, "ocr_output_tokens": 700, "ocr_cost_jpy": 1.12, "ocr_cost_usd": 0.0075, "ocr_succeeded": True},
            ),
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
    assert body["quote_mode"] == "exact"
    assert body["estimate_source"] == "vision_ocr"
    assert body["estimated_tokens"] > 0
    assert body["price_jpy"] > 0
    assert body["contract_text"] == ocr_text
    assert body["quote_token"] == "quote-test-token"


# -- Clause preview edge cases -----------------------------------------------


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
    with patch("backend.routers.upload._extract_clause_preview", return_value=(None, None, None, None)):
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
    assert body["is_contract"] is None


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
        settings.PRICING_POLICY_FILE = "backend/data/pricing_policy.json"

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/upload",
                data={"input_type": "text", "text": huge_text},
            )
    assert resp.status_code == 413
