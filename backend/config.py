from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # OpenAI
    OPENAI_API_KEY: str

    # Environment
    APP_ENV: Literal["development", "production"] = "development"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/contract_checker"

    # Redis
    REDIS_URL: str = "redis://redis:6379"

    # KOMOJU Payment
    KOMOJU_SECRET_KEY: str = ""
    KOMOJU_PUBLISHABLE_KEY: str = ""
    KOMOJU_WEBHOOK_SECRET: str = ""

    # Resend Email
    RESEND_API_KEY: str = ""

    # Sentry
    SENTRY_DSN: str = ""

    # PostHog
    POSTHOG_API_KEY: str = ""
    POSTHOG_HOST: str = "https://app.posthog.com"

    # App
    FRONTEND_URL: str = "http://localhost:5173"
    REPORT_TTL_HOURS: int = 24

    model_config = SettingsConfigDict(env_file=".env")

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    def should_bootstrap_db(self) -> bool:
        return self.is_development

    def uses_local_frontend_url(self) -> bool:
        host = urlparse(self.FRONTEND_URL).hostname or ""
        return host in {"localhost", "127.0.0.1"}

    def validate_runtime(self) -> None:
        if not self.is_production:
            return

        missing = []
        required_fields = {
            "KOMOJU_SECRET_KEY": self.KOMOJU_SECRET_KEY,
            "KOMOJU_PUBLISHABLE_KEY": self.KOMOJU_PUBLISHABLE_KEY,
            "KOMOJU_WEBHOOK_SECRET": self.KOMOJU_WEBHOOK_SECRET,
            "RESEND_API_KEY": self.RESEND_API_KEY,
        }
        for field_name, value in required_fields.items():
            if not value:
                missing.append(field_name)

        if self.uses_local_frontend_url():
            missing.append("FRONTEND_URL (must not point to localhost in production)")

        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Invalid production configuration: {joined}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
