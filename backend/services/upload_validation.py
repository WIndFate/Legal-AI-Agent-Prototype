"""Upload validation: MIME type detection and file size enforcement."""
from __future__ import annotations

import filetype
from fastapi import HTTPException

# Only these MIME types are accepted at the upload endpoint.
ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


def detect_and_validate_mime(data: bytes) -> str:
    """Detect real MIME type from magic bytes. Raises 415 if type is not allowed.

    Never trusts the client-supplied Content-Type header.
    """
    kind = filetype.guess(data)
    actual = kind.mime if kind else None
    if actual not in ALLOWED_MIMES:
        raise HTTPException(
            status_code=415,
            detail="upload_unsupported_type",
        )
    return actual


def check_upload_file_size(data: bytes, mime: str, settings) -> None:
    """Raise 413 if file exceeds the per-type size cap."""
    if mime == "application/pdf":
        max_bytes = settings.MAX_UPLOAD_PDF_MB * 1024 * 1024
        code = "upload_too_large"
    else:
        max_bytes = settings.MAX_UPLOAD_IMAGE_MB * 1024 * 1024
        code = "upload_too_large"

    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=code)
