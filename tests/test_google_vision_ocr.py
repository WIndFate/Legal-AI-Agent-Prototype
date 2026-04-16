from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.services.google_vision_ocr import (
    extract_text_from_image_with_snapshot,
    extract_text_from_pdf_with_snapshot,
)


@pytest.mark.asyncio
async def test_extract_text_from_image_with_snapshot_uses_google_vision():
    fake_response = SimpleNamespace(
        full_text_annotation=SimpleNamespace(text="第1条 テスト契約"),
        error=SimpleNamespace(message=""),
    )
    fake_client = SimpleNamespace(document_text_detection=lambda image: fake_response)  # noqa: ARG005

    with patch(
        "backend.services.google_vision_ocr.vision.ImageAnnotatorClient",
        return_value=fake_client,
    ):
        text, snapshot = await extract_text_from_image_with_snapshot(b"image-bytes", "image/png")

    assert text == "第1条 テスト契約"
    assert snapshot["ocr_model"] == "google-vision-document-text"
    assert snapshot["ocr_pages"] == 1
    assert snapshot["ocr_cost_jpy"] == 0.225


@pytest.mark.asyncio
async def test_extract_text_from_pdf_with_snapshot_converts_each_page():
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
        patch(
            "backend.services.google_vision_ocr.vision.ImageAnnotatorClient",
            return_value=fake_client,
        ),
        patch(
            "backend.services.google_vision_ocr.convert_from_bytes",
            return_value=[FakePage(), FakePage()],
        ),
    ):
        text, snapshot = await extract_text_from_pdf_with_snapshot(b"%PDF")

    assert "第1条 テスト契約" in text
    assert snapshot["ocr_pages"] == 2
    assert snapshot["ocr_cost_jpy"] == 0.45


@pytest.mark.asyncio
async def test_extract_text_from_image_with_snapshot_raises_on_api_error():
    fake_response = SimpleNamespace(
        full_text_annotation=SimpleNamespace(text=""),
        error=SimpleNamespace(message="quota exceeded"),
    )
    fake_client = SimpleNamespace(document_text_detection=lambda image: fake_response)  # noqa: ARG005

    with patch(
        "backend.services.google_vision_ocr.vision.ImageAnnotatorClient",
        return_value=fake_client,
    ):
        with pytest.raises(RuntimeError, match="quota exceeded"):
            await extract_text_from_image_with_snapshot(b"image-bytes", "image/png")
