from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # OpenAI
    OPENAI_API_KEY: str

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


def get_settings() -> Settings:
    return Settings()
