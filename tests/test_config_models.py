from backend.config import get_settings


def test_default_model_settings(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.OCR_MODEL == "gpt-4o"
    assert settings.ANALYSIS_MODEL == "gpt-4o"
    assert settings.PARSE_MODEL == "gpt-4o-mini"
    assert settings.SUGGESTION_MODEL == "gpt-4o-mini"
    assert settings.TRANSLATION_MODEL == "gpt-4o-mini"

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
