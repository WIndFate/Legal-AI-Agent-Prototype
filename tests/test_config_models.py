from backend.config import get_settings


def test_default_model_settings(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.OCR_MODEL == "google-vision-document-text"
    assert settings.ANALYSIS_MODEL == "gpt-4o"
    assert settings.PARSE_MODEL == "gpt-4o-mini"
    assert settings.SUGGESTION_MODEL == "gpt-4o-mini"
    assert settings.TRANSLATION_MODEL == "gpt-4o-mini"
    assert settings.DAILY_COST_BUDGET_JPY == 500.0
    assert settings.OCR_WASTE_DAILY_LIMIT == 10

    get_settings.cache_clear()


def test_model_settings_can_be_overridden(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("PARSE_MODEL", "custom-parse")
    monkeypatch.setenv("SUGGESTION_MODEL", "custom-suggestion")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.PARSE_MODEL == "custom-parse"
    assert settings.SUGGESTION_MODEL == "custom-suggestion"

    get_settings.cache_clear()


def test_production_requires_admin_api_token(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@db.example.com/app")
    monkeypatch.setenv("REDIS_URL", "redis://cache.example.com:6379/0")
    monkeypatch.setenv("FRONTEND_URL", "https://contractguard.jp")
    monkeypatch.setenv("KOMOJU_SECRET_KEY", "sk_live")
    monkeypatch.setenv("KOMOJU_PUBLISHABLE_KEY", "pk_live")
    monkeypatch.setenv("KOMOJU_WEBHOOK_SECRET", "whsec_live")
    monkeypatch.setenv("RESEND_API_KEY", "re_live")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", "base64-creds")
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    try:
        try:
            settings.validate_runtime()
            raise AssertionError("validate_runtime() should require ADMIN_API_TOKEN")
        except ValueError as exc:
            assert "ADMIN_API_TOKEN" in str(exc)
    finally:
        get_settings.cache_clear()
