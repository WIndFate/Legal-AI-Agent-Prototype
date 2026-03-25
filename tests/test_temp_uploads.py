from backend.config import get_settings
from backend.services.temp_uploads import delete_temp_upload, get_temp_upload_path, read_temp_upload, stage_temp_upload


def test_stage_read_and_delete_temp_upload(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_STAGING_DIR", str(tmp_path))
    get_settings.cache_clear()

    token = stage_temp_upload(b"contract-bytes", "sample.pdf")
    path = get_temp_upload_path(token)

    assert path.exists()
    assert path.suffix == ".pdf"
    assert read_temp_upload(token) == b"contract-bytes"

    delete_temp_upload(token)
    assert not path.exists()

    get_settings.cache_clear()
