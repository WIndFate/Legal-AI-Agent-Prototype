"""Integration tests for POST /api/upload endpoint."""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from redis.exceptions import RedisError

from backend.routers.upload import _extract_clause_preview, preview_llm, router

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
        patch("backend.routers.upload.check_budget_allowed", new_callable=AsyncMock, return_value=True),
        patch("backend.routers.upload.record_cost", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.upload.load_cached_quote", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.upload.store_cached_quote", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.upload.build_quote_token", return_value="quote-test-token"),
        # Abuse guard defaults: allow OCR, silent record/rollback (redis=None would fail-closed otherwise)
        patch("backend.routers.upload.check_ocr_allowed", new_callable=AsyncMock, return_value=True),
        patch("backend.routers.upload.record_ocr_upload", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.upload.rollback_ocr_upload", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.upload.load_ocr_result_cache", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.upload.store_ocr_result_cache", new_callable=AsyncMock, return_value=None),
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
                {"ocr_model": "google-vision-document-text", "ocr_input_tokens": 1, "ocr_output_tokens": 400, "ocr_cost_jpy": 0.225, "ocr_cost_usd": 0.0015, "ocr_succeeded": True},
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
                {"ocr_model": "google-vision-document-text", "ocr_input_tokens": 1, "ocr_output_tokens": 120, "ocr_cost_jpy": 0.225, "ocr_cost_usd": 0.0015, "ocr_succeeded": True},
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


def test_extract_clause_preview_short_non_contract_still_sets_is_contract_false():
    """Short OCR fragments should still be classified as non-contract material."""

    class _FakeResponse:
        content = '{"is_contract": false, "clauses": []}'

    with (
        patch.object(type(preview_llm), "invoke", return_value=_FakeResponse()),
        patch("backend.routers.upload.log_model_usage"),
        patch(
            "backend.routers.upload.extract_usage",
            return_value={"input_tokens": 32, "output_tokens": 8, "cached_input_tokens": 0},
        ),
    ):
        preview, clause_count, snapshot, is_contract = _extract_clause_preview("Leon S. Kennedy Ada Wong")

    assert preview is None
    assert clause_count is None
    assert snapshot is not None
    assert snapshot["preview_succeeded"] is True
    assert is_contract is False


def test_extract_clause_preview_short_contract_sets_is_contract_without_preview():
    """Short contract snippets should still surface contract detection even without preview clauses."""

    class _FakeResponse:
        content = '{"is_contract": true, "clauses": []}'

    with (
        patch.object(type(preview_llm), "invoke", return_value=_FakeResponse()),
        patch("backend.routers.upload.log_model_usage"),
        patch(
            "backend.routers.upload.extract_usage",
            return_value={"input_tokens": 40, "output_tokens": 10, "cached_input_tokens": 0},
        ),
    ):
        preview, clause_count, snapshot, is_contract = _extract_clause_preview("業務委託契約書 契約期間 1年")

    assert preview is None
    assert clause_count is None
    assert snapshot is not None
    assert snapshot["preview_succeeded"] is True
    assert is_contract is True


@pytest.mark.asyncio
async def test_upload_image_empty_ocr_returns_zero_price():
    """Image that yields no OCR text should return zero-price response."""
    fake_image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    with patch(
        "backend.routers.upload.extract_text_from_image_with_snapshot",
        new_callable=AsyncMock,
        return_value=("", {"ocr_model": "google-vision-document-text", "ocr_input_tokens": 1, "ocr_output_tokens": 0, "ocr_cost_jpy": 0.225, "ocr_cost_usd": 0.0015, "ocr_succeeded": True}),
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
        patch("backend.routers.upload.precheck_pdf_pages", return_value=page_count),
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
        patch("backend.routers.upload.precheck_pdf_pages", return_value=page_count),
        patch(
            "backend.routers.upload.extract_text_from_pdf_text_layer",
            return_value=("", page_count),
        ),
        patch(
            "backend.routers.upload.pdf_text_layer_is_sufficient",
            return_value=False,
        ),
        patch(
            "backend.routers.upload.extract_text_from_pdf_with_snapshot_using_page_count",
            new_callable=AsyncMock,
            return_value=(
                ocr_text,
                {"ocr_model": "google-vision-document-text", "ocr_input_tokens": 3, "ocr_output_tokens": 700, "ocr_cost_jpy": 0.675, "ocr_cost_usd": 0.0045, "ocr_succeeded": True},
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
        settings.MAX_UPLOAD_TEXT_CHARS = 1_000_000  # high enough to not trigger text char limit
        settings.MAX_UPLOAD_IMAGE_MB = 25
        settings.MAX_UPLOAD_PDF_MB = 30
        settings.PRICING_POLICY_FILE = "backend/data/pricing_policy.json"

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/upload",
                data={"input_type": "text", "text": huge_text},
            )
    assert resp.status_code == 413


# -- P0-1: file size limits --------------------------------------------------


@pytest.mark.asyncio
async def test_upload_rejects_oversized_image():
    """Image files over 25 MB should be rejected with 413 before OCR is called."""
    oversized_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * (26 * 1024 * 1024)  # JPEG magic + 26 MB

    with patch("backend.routers.upload.extract_text_from_image_with_snapshot") as mock_ocr:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/upload",
                data={"input_type": "image"},
                files={"file": ("big.jpg", io.BytesIO(oversized_bytes), "image/jpeg")},
            )
    assert resp.status_code == 413
    assert resp.json()["detail"] == "upload_too_large"
    mock_ocr.assert_not_called()


@pytest.mark.asyncio
async def test_upload_rejects_oversized_pdf():
    """PDF files over 30 MB should be rejected with 413 before OCR is called."""
    oversized_bytes = b"%PDF-1.4" + b"\x00" * (31 * 1024 * 1024)  # PDF magic + 31 MB

    with (
        patch("backend.routers.upload.extract_text_from_pdf_with_snapshot_using_page_count") as mock_ocr,
        patch("backend.routers.upload.extract_text_from_pdf_text_layer", return_value=("", 1)),
        patch("backend.routers.upload.pdf_text_layer_is_sufficient", return_value=False),
        patch("backend.routers.upload.precheck_pdf_pages", return_value=1),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/upload",
                data={"input_type": "pdf"},
                files={"file": ("big.pdf", io.BytesIO(oversized_bytes), "application/pdf")},
            )
    assert resp.status_code == 413
    assert resp.json()["detail"] == "upload_too_large"
    mock_ocr.assert_not_called()


@pytest.mark.asyncio
async def test_upload_rejects_pdf_over_page_cap():
    """PDF with more than MAX_UPLOAD_PAGES pages should be rejected before OCR is called."""
    fake_pdf = b"%PDF-1.4" + b"\x00" * 100

    with (
        patch(
            "backend.routers.upload.extract_text_from_pdf_with_snapshot_using_page_count"
        ) as mock_vision_ocr,
        patch("backend.routers.upload.precheck_pdf_pages", side_effect=Exception("upload_too_many_pages")),
    ):
        from fastapi import HTTPException as FastAPIHTTPException
        with patch(
            "backend.routers.upload.precheck_pdf_pages",
            side_effect=FastAPIHTTPException(status_code=413, detail="upload_too_many_pages"),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/upload",
                    data={"input_type": "pdf"},
                    files={"file": ("many_pages.pdf", io.BytesIO(fake_pdf), "application/pdf")},
                )
    assert resp.status_code == 413
    assert resp.json()["detail"] == "upload_too_many_pages"
    mock_vision_ocr.assert_not_called()


@pytest.mark.asyncio
async def test_upload_image_returns_503_when_daily_budget_exhausted():
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
async def test_upload_rejects_mime_mismatch():
    """Files whose magic bytes do not match a supported MIME type should be rejected with 415."""
    exe_bytes = b"MZ\x90\x00" + b"\x00" * 100  # PE/EXE magic bytes

    with patch("backend.routers.upload.extract_text_from_image_with_snapshot") as mock_ocr:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/upload",
                data={"input_type": "image"},
                files={"file": ("evil.exe", io.BytesIO(exe_bytes), "image/png")},
            )
    assert resp.status_code == 415
    assert resp.json()["detail"] == "upload_unsupported_type"
    mock_ocr.assert_not_called()


@pytest.mark.asyncio
async def test_upload_accepts_detected_jpeg_despite_octet_stream_header():
    """A valid JPEG should pass even when the client declares application/octet-stream."""
    jpeg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100

    with patch(
        "backend.routers.upload.extract_text_from_image_with_snapshot",
        new_callable=AsyncMock,
        return_value=("第1条 業務委託", {"ocr_succeeded": True, "ocr_mime_type": "image/jpeg"}),
    ) as mock_ocr:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/upload",
                data={"input_type": "image"},
                files={"file": ("contract.jpg", io.BytesIO(jpeg_bytes), "application/octet-stream")},
            )

    assert resp.status_code == 200
    assert resp.json()["estimate_source"] == "vision_ocr"
    mock_ocr.assert_awaited_once_with(jpeg_bytes, "image/jpeg")


@pytest.mark.asyncio
async def test_upload_text_too_long():
    """Text input over MAX_UPLOAD_TEXT_CHARS (80000) should be rejected with 413."""
    long_text = "第1条 " * 30000  # well over 80000 chars

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/upload",
            data={"input_type": "text", "text": long_text},
        )
    assert resp.status_code == 413
    assert resp.json()["detail"] == "upload_text_too_long"


# -- P0-1: OCR abuse guard ---------------------------------------------------


@pytest.mark.asyncio
async def test_abuse_guard_blocks_fourth_unpaid_upload():
    """After 3 unpaid OCR uploads, the 4th should return 429 before OCR is called."""
    fake_image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50

    with (
        patch("backend.routers.upload.load_ocr_result_cache", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.upload.check_ocr_allowed", new_callable=AsyncMock, return_value=False),
        patch("backend.routers.upload.extract_text_from_image_with_snapshot") as mock_ocr,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/upload",
                data={"input_type": "image"},
                files={"file": ("contract4.png", io.BytesIO(fake_image), "image/png")},
            )
    assert resp.status_code == 429
    assert resp.json()["detail"] == "upload_banned"
    mock_ocr.assert_not_called()


@pytest.mark.asyncio
async def test_abuse_guard_same_hash_does_not_count():
    """Uploading the same image (same file hash) hits OCR cache and skips abuse guard."""
    fake_image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
    cached_result = {"text": "第1条 業務委託", "snapshot": {"ocr_succeeded": True}}

    with (
        patch("backend.routers.upload.load_ocr_result_cache", new_callable=AsyncMock, return_value=cached_result),
        patch("backend.routers.upload.check_ocr_allowed", new_callable=AsyncMock) as mock_check,
        patch("backend.routers.upload.record_ocr_upload", new_callable=AsyncMock) as mock_record,
        patch("backend.routers.upload.extract_text_from_image_with_snapshot") as mock_ocr,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/upload",
                data={"input_type": "image"},
                files={"file": ("same.png", io.BytesIO(fake_image), "image/png")},
            )
    assert resp.status_code == 200
    # Abuse guard should not be consulted or incremented for cache hits
    mock_check.assert_not_called()
    mock_record.assert_not_called()
    mock_ocr.assert_not_called()


@pytest.mark.asyncio
async def test_abuse_guard_rollback_on_ocr_failure():
    """If Vision OCR raises an exception, record_ocr_upload should be rolled back."""
    fake_image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50

    with (
        patch("backend.routers.upload.load_ocr_result_cache", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.upload.check_ocr_allowed", new_callable=AsyncMock, return_value=True),
        patch("backend.routers.upload.record_ocr_upload", new_callable=AsyncMock) as mock_record,
        patch("backend.routers.upload.rollback_ocr_upload", new_callable=AsyncMock) as mock_rollback,
        patch(
            "backend.routers.upload.extract_text_from_image_with_snapshot",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Vision API timeout"),
        ),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with pytest.raises(RuntimeError, match="Vision API timeout"):
                await client.post(
                    "/api/upload",
                    data={"input_type": "image"},
                    files={"file": ("contract.png", io.BytesIO(fake_image), "image/png")},
                )
    # Verify rollback was called even though OCR raised
    mock_record.assert_called_once()
    mock_rollback.assert_called_once()


@pytest.mark.asyncio
async def test_abuse_guard_redis_down_fail_closed_with_503():
    """When Redis is unavailable, OCR should fail-closed with 503."""
    fake_image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50

    with (
        patch("backend.routers.upload.load_ocr_result_cache", new_callable=AsyncMock, return_value=None),
        patch(
            "backend.routers.upload.check_ocr_allowed",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=503, detail="service_unavailable"),
        ),
        patch("backend.routers.upload.extract_text_from_image_with_snapshot") as mock_ocr,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/upload",
                data={"input_type": "image"},
                files={"file": ("contract.png", io.BytesIO(fake_image), "image/png")},
            )
    assert resp.status_code == 503
    assert resp.json()["detail"] == "service_unavailable"
    mock_ocr.assert_not_called()
