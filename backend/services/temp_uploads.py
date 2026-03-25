import os
import uuid
from pathlib import Path

from backend.config import get_settings


def _staging_dir() -> Path:
    settings = get_settings()
    path = Path(settings.UPLOAD_STAGING_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_suffix(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix and suffix.isascii() and len(suffix) <= 10:
        return suffix
    return ""


def stage_temp_upload(data: bytes, filename: str | None = None) -> str:
    """Persist an uploaded file temporarily and return its opaque token."""
    token = f"{uuid.uuid4().hex}{_safe_suffix(filename)}"
    path = _staging_dir() / token
    path.write_bytes(data)
    return token


def get_temp_upload_path(token: str) -> Path:
    """Resolve a staging token to an on-disk path inside the staging dir."""
    safe_name = os.path.basename(token)
    return _staging_dir() / safe_name


def read_temp_upload(token: str) -> bytes:
    """Read staged upload bytes."""
    return get_temp_upload_path(token).read_bytes()


def delete_temp_upload(token: str | None) -> None:
    """Delete a staged upload if it still exists."""
    if not token:
        return
    path = get_temp_upload_path(token)
    if path.exists():
        path.unlink()
