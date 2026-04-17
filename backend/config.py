from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict

# Hostnames that are unambiguously local/development. Anything else is treated as
# potentially production and triggers the APP_ENV guard in validate_runtime().
_LOCAL_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "postgres",
    "redis",
    "backend",
    "frontend",
    "host.docker.internal",
}


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # OpenAI
    OPENAI_API_KEY: str
    OCR_MODEL: str = "google-vision-document-text"
    ANALYSIS_MODEL: str = "gpt-4o"
    PARSE_MODEL: str = "gpt-4o-mini"
    SUGGESTION_MODEL: str = "gpt-4o-mini"
    TRANSLATION_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    COST_ESTIMATE_VERSION: str = "2026-03-28-v1"
    GOOGLE_APPLICATION_CREDENTIALS_JSON: str = ""
    GOOGLE_VISION_PROJECT_ID: str = ""
    DAILY_COST_BUDGET_JPY: float = 500.0
    GOOGLE_VISION_COST_PER_PAGE_JPY: float = 0.225

    # Environment
    APP_ENV: Literal["development", "production"] = "development"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/contract_checker"
    AUTO_APPLY_MIGRATIONS: bool = True
    DB_STARTUP_TIMEOUT_SECONDS: int = 90
    MIGRATION_LOCK_ID: int = 20260328

    # Redis
    REDIS_URL: str = "redis://redis:6379"

    # KOMOJU Payment
    KOMOJU_SECRET_KEY: str = ""
    KOMOJU_PUBLISHABLE_KEY: str = ""
    KOMOJU_WEBHOOK_SECRET: str = ""

    # Resend Email
    RESEND_API_KEY: str = ""
    EMAIL_FROM_ADDRESS: str = "noreply@mail.contractguard.jp"
    EMAIL_FROM_NAME: str = "ContractGuard"
    EMAIL_REPLY_TO: str = "support@contractguard.jp"

    # Sentry
    SENTRY_DSN: str = ""

    # PostHog
    POSTHOG_API_KEY: str = ""
    POSTHOG_HOST: str = "https://app.posthog.com"

    # App
    FRONTEND_URL: str = "http://localhost:5173"
    ADMIN_API_TOKEN: str = ""
    REPORT_TTL_HOURS: int = 72
    MAX_UPLOAD_PAGES: int = 20
    MAX_UPLOAD_IMAGE_MB: int = 25
    MAX_UPLOAD_PDF_MB: int = 30
    MAX_UPLOAD_TEXT_CHARS: int = 80_000
    MAX_CONTRACT_TOKENS: int = 60000
    OCR_WASTE_DAILY_LIMIT: int = 10
    OCR_WASTE_WINDOW_SECONDS: int = 86_400
    UPLOAD_RATE_LIMIT_COUNT: int = 30
    UPLOAD_RATE_LIMIT_WINDOW_SECONDS: int = 600
    PREVIEW_RATE_LIMIT_COUNT: int = 8
    PREVIEW_RATE_LIMIT_WINDOW_SECONDS: int = 600
    QUOTE_CACHE_TTL_SECONDS: int = 21600
    PRICING_POLICY_FILE: str = "backend/data/pricing_policy.json"
    COST_SAMPLE_SEED_FILE: str = "backend/data/cost_samples_seed.json"
    COST_SAMPLE_MINIMUM: int = 10

    model_config = SettingsConfigDict(env_file=".env")

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    def uses_local_frontend_url(self) -> bool:
        host = urlparse(self.FRONTEND_URL).hostname or ""
        return host in {"localhost", "127.0.0.1"}

    def _looks_remote(self, value: str) -> bool:
        """Return True when a URL hostname looks like an externally hosted service."""
        host = (urlparse(value).hostname or "").lower()
        if not host:
            return False
        return host not in _LOCAL_HOSTNAMES

    def validate_runtime(self) -> None:
        # Guardrail: if any critical URL points at an external host, refuse to boot
        # in non-production mode. This catches the deploy-time mistake of forgetting
        # to set APP_ENV=production, which would otherwise enable the dev payment
        # bypass and the lenient CORS list against real infrastructure.
        if not self.is_production:
            remote_urls = {
                "DATABASE_URL": self._looks_remote(self.DATABASE_URL),
                "REDIS_URL": self._looks_remote(self.REDIS_URL),
                "FRONTEND_URL": self._looks_remote(self.FRONTEND_URL),
            }
            offenders = [name for name, is_remote in remote_urls.items() if is_remote]
            if offenders:
                joined = ", ".join(offenders)
                raise ValueError(
                    "Refusing to start: APP_ENV is not 'production' but the following "
                    f"URLs point at remote hosts: {joined}. Set APP_ENV=production or "
                    "switch these URLs back to local hostnames."
                )
            return

        missing = []
        required_fields = {
            "KOMOJU_SECRET_KEY": self.KOMOJU_SECRET_KEY,
            "KOMOJU_PUBLISHABLE_KEY": self.KOMOJU_PUBLISHABLE_KEY,
            "KOMOJU_WEBHOOK_SECRET": self.KOMOJU_WEBHOOK_SECRET,
            "RESEND_API_KEY": self.RESEND_API_KEY,
            "GOOGLE_APPLICATION_CREDENTIALS_JSON": self.GOOGLE_APPLICATION_CREDENTIALS_JSON,
            "ADMIN_API_TOKEN": self.ADMIN_API_TOKEN,
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
