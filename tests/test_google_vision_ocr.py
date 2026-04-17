from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from google.api_core import exceptions as google_exceptions

from backend.services.google_vision_ocr import (
    extract_text_from_image_with_snapshot,
    extract_text_from_pdf_with_snapshot,
    extract_text_from_pdf_with_snapshot_using_page_count,
)


@pytest.fixture(autouse=True)
def _reset_cached_vision_client():
    with patch("backend.services.google_vision_ocr._vision_client", None):
        yield


@pytest.mark.asyncio
async def test_extract_text_from_image_with_snapshot_uses_google_vision():
    fake_settings = SimpleNamespace(
        OCR_MODEL="google-vision-document-text",
        GOOGLE_VISION_COST_PER_PAGE_JPY=0.225,
        GOOGLE_APPLICATION_CREDENTIALS_JSON="encoded-json",
    )
    fake_response = SimpleNamespace(
        full_text_annotation=SimpleNamespace(text="第1条 テスト契約"),
        error=SimpleNamespace(message=""),
    )
    fake_client = SimpleNamespace(document_text_detection=lambda image: fake_response)  # noqa: ARG005

    with (
        patch("backend.services.google_vision_ocr.get_settings", return_value=fake_settings),
        patch(
            "backend.services.google_vision_ocr.vision.ImageAnnotatorClient",
            return_value=fake_client,
        ),
    ):
        text, snapshot = await extract_text_from_image_with_snapshot(b"image-bytes", "image/png")

    assert text == "第1条 テスト契約"
    assert snapshot["ocr_model"] == "google-vision-document-text"
    assert snapshot["ocr_pages"] == 1
    assert snapshot["ocr_cost_jpy"] == 0.225


@pytest.mark.asyncio
async def test_extract_text_from_pdf_with_snapshot_converts_each_page():
    fake_settings = SimpleNamespace(
        OCR_MODEL="google-vision-document-text",
        GOOGLE_VISION_COST_PER_PAGE_JPY=0.225,
        GOOGLE_APPLICATION_CREDENTIALS_JSON="encoded-json",
    )
    fake_response = SimpleNamespace(
        full_text_annotation=SimpleNamespace(text="第1条 テスト契約"),
        error=SimpleNamespace(message=""),
    )
    fake_client = SimpleNamespace(document_text_detection=lambda image: fake_response)  # noqa: ARG005

    class FakePage:
        def save(self, buffer, format):  # noqa: ARG002
            buffer.write(b"png")

        def close(self):
            return None

    with (
        patch("backend.services.google_vision_ocr.get_settings", return_value=fake_settings),
        patch(
            "backend.services.google_vision_ocr.vision.ImageAnnotatorClient",
            return_value=fake_client,
        ),
        patch(
            "backend.services.google_vision_ocr.PdfReader",
            return_value=SimpleNamespace(pages=[object(), object()]),
        ),
        patch(
            "backend.services.google_vision_ocr.convert_from_bytes",
            side_effect=[[FakePage()], [FakePage()]],
        ),
    ):
        text, snapshot = await extract_text_from_pdf_with_snapshot(b"%PDF")

    assert "第1条 テスト契約" in text
    assert snapshot["ocr_pages"] == 2
    assert snapshot["ocr_cost_jpy"] == 0.45


@pytest.mark.asyncio
async def test_extract_text_from_pdf_with_snapshot_renders_one_page_at_a_time():
    fake_settings = SimpleNamespace(
        OCR_MODEL="google-vision-document-text",
        GOOGLE_VISION_COST_PER_PAGE_JPY=0.225,
        GOOGLE_APPLICATION_CREDENTIALS_JSON="encoded-json",
    )
    fake_response = SimpleNamespace(
        full_text_annotation=SimpleNamespace(text="第1条 テスト契約"),
        error=SimpleNamespace(message=""),
    )
    fake_client = SimpleNamespace(document_text_detection=lambda image: fake_response)  # noqa: ARG005

    class FakePage:
        def save(self, buffer, format):  # noqa: ARG002
            buffer.write(b"png")

        def close(self):
            return None

    with (
        patch("backend.services.google_vision_ocr.get_settings", return_value=fake_settings),
        patch(
            "backend.services.google_vision_ocr.vision.ImageAnnotatorClient",
            return_value=fake_client,
        ),
        patch(
            "backend.services.google_vision_ocr.PdfReader",
            return_value=SimpleNamespace(pages=[object(), object(), object()]),
        ),
        patch(
            "backend.services.google_vision_ocr.convert_from_bytes",
            side_effect=[[FakePage()], [FakePage()], [FakePage()]],
        ) as mock_convert,
    ):
        text, snapshot = await extract_text_from_pdf_with_snapshot(b"%PDF")

    assert text.count("第1条 テスト契約") == 3
    assert snapshot["ocr_pages"] == 3
    assert [call.kwargs["first_page"] for call in mock_convert.call_args_list] == [1, 2, 3]
    assert [call.kwargs["last_page"] for call in mock_convert.call_args_list] == [1, 2, 3]


@pytest.mark.asyncio
async def test_extract_text_from_pdf_with_snapshot_reuses_single_cached_client():
    fake_settings = SimpleNamespace(
        OCR_MODEL="google-vision-document-text",
        GOOGLE_VISION_COST_PER_PAGE_JPY=0.225,
        GOOGLE_APPLICATION_CREDENTIALS_JSON="encoded-json",
    )
    fake_response = SimpleNamespace(
        full_text_annotation=SimpleNamespace(text="第1条 テスト契約"),
        error=SimpleNamespace(message=""),
    )
    fake_client = SimpleNamespace(document_text_detection=lambda image: fake_response)  # noqa: ARG005

    class FakePage:
        def save(self, buffer, format):  # noqa: ARG002
            buffer.write(b"png")

        def close(self):
            return None

    with (
        patch("backend.services.google_vision_ocr.get_settings", return_value=fake_settings),
        patch("backend.services.google_vision_ocr._vision_client", None),
        patch(
            "backend.services.google_vision_ocr.vision.ImageAnnotatorClient",
            return_value=fake_client,
        ) as mock_client_ctor,
        patch(
            "backend.services.google_vision_ocr.convert_from_bytes",
            side_effect=[[FakePage()], [FakePage()], [FakePage()]],
        ),
    ):
        text, snapshot = await extract_text_from_pdf_with_snapshot_using_page_count(b"%PDF", 3)

    assert text.count("第1条 テスト契約") == 3
    assert snapshot["ocr_pages"] == 3
    mock_client_ctor.assert_called_once()


@pytest.mark.asyncio
async def test_extract_text_from_image_with_snapshot_returns_billing_error_code():
    fake_settings = SimpleNamespace(
        OCR_MODEL="google-vision-document-text",
        GOOGLE_VISION_COST_PER_PAGE_JPY=0.225,
        GOOGLE_APPLICATION_CREDENTIALS_JSON="encoded-json",
    )
    fake_client = SimpleNamespace(
        document_text_detection=lambda image: (_ for _ in ()).throw(  # noqa: ARG005
            google_exceptions.PermissionDenied("This API method requires billing to be enabled.")
        )
    )

    with (
        patch("backend.services.google_vision_ocr.get_settings", return_value=fake_settings),
        patch(
            "backend.services.google_vision_ocr.vision.ImageAnnotatorClient",
            return_value=fake_client,
        ),
    ):
        with pytest.raises(HTTPException) as excinfo:
            await extract_text_from_image_with_snapshot(b"image-bytes", "image/png")

    assert excinfo.value.status_code == 503
    assert excinfo.value.detail == "google_vision_billing_disabled"


@pytest.mark.asyncio
async def test_extract_text_from_image_with_snapshot_returns_permission_error_code():
    fake_settings = SimpleNamespace(
        OCR_MODEL="google-vision-document-text",
        GOOGLE_VISION_COST_PER_PAGE_JPY=0.225,
        GOOGLE_APPLICATION_CREDENTIALS_JSON="encoded-json",
    )
    fake_response = SimpleNamespace(
        full_text_annotation=SimpleNamespace(text=""),
        error=SimpleNamespace(message="Permission denied on resource project."),
    )
    fake_client = SimpleNamespace(document_text_detection=lambda image: fake_response)  # noqa: ARG005

    with (
        patch("backend.services.google_vision_ocr.get_settings", return_value=fake_settings),
        patch(
            "backend.services.google_vision_ocr.vision.ImageAnnotatorClient",
            return_value=fake_client,
        ),
    ):
        with pytest.raises(HTTPException) as excinfo:
            await extract_text_from_image_with_snapshot(b"image-bytes", "image/png")

    assert excinfo.value.status_code == 503
    assert excinfo.value.detail == "google_vision_permission_denied"


@pytest.mark.asyncio
async def test_extract_text_from_image_with_snapshot_returns_not_configured_when_missing_credentials(
    monkeypatch,
):
    fake_settings = SimpleNamespace(
        OCR_MODEL="google-vision-document-text",
        GOOGLE_VISION_COST_PER_PAGE_JPY=0.225,
        GOOGLE_APPLICATION_CREDENTIALS_JSON="",
    )
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

    with patch("backend.services.google_vision_ocr.get_settings", return_value=fake_settings):
        with pytest.raises(HTTPException) as excinfo:
            await extract_text_from_image_with_snapshot(b"image-bytes", "image/png")

    assert excinfo.value.status_code == 503
    assert excinfo.value.detail == "google_vision_not_configured"
