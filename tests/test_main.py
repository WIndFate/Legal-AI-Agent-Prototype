from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import mock_open, patch

from backend.main import _configure_google_credentials


def test_configure_google_credentials_writes_private_file_permissions():
    fake_settings = SimpleNamespace(
        GOOGLE_APPLICATION_CREDENTIALS_JSON="ZW5jb2RlZA==",
        GOOGLE_VISION_PROJECT_ID="test-project",
    )

    env: dict[str, str] = {}
    with (
        patch("builtins.open", mock_open()) as mocked_open,
        patch("backend.main.os.chmod") as mock_chmod,
        patch.dict(os.environ, env, clear=True),
    ):
        _configure_google_credentials(fake_settings)
        assert os.environ["GOOGLE_APPLICATION_CREDENTIALS"] == "/tmp/gcp-sa.json"
        assert os.environ["GOOGLE_CLOUD_PROJECT"] == "test-project"

    mocked_open.assert_called_once_with("/tmp/gcp-sa.json", "wb")
    mock_chmod.assert_called_once_with("/tmp/gcp-sa.json", 0o600)
