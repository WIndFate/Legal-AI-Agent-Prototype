import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from backend.config import get_settings
from backend.rag.loader import load_legal_knowledge
from backend.routers import analysis, health, upload, payment, report, referral, eval

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.validate_runtime()

    if settings.is_production and not settings.SENTRY_DSN:
        logger.warning("APP_ENV=production but SENTRY_DSN is not configured.")
    if settings.is_production and not settings.POSTHOG_API_KEY:
        logger.warning("APP_ENV=production but POSTHOG_API_KEY is not configured.")

    # Initialize RAG knowledge base
    logger.info("Loading legal knowledge into RAG store...")
    try:
        count = await load_legal_knowledge()
        logger.info(f"Loaded {count} legal knowledge documents.")
    except Exception as e:
        logger.warning(f"Failed to load legal knowledge (will retry on first request): {e}")

    # Initialize Sentry
    if settings.SENTRY_DSN:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            traces_sample_rate=0.1,
            before_send=_filter_pii,
        )
        logger.info("Sentry initialized.")

    # Initialize PostHog
    if settings.POSTHOG_API_KEY:
        import posthog
        posthog.api_key = settings.POSTHOG_API_KEY
        posthog.host = settings.POSTHOG_HOST
        logger.info("PostHog initialized.")

    # Start scheduled cleanup (expired reports + contract text nullification)
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from backend.services.cleanup import run_cleanup

    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_cleanup, "interval", hours=1, id="cleanup")
    scheduler.start()
    logger.info("APScheduler cleanup job started (every 1h).")

    yield

    scheduler.shutdown()


def _filter_pii(event, hint):
    """Remove contract text from Sentry events to protect user privacy."""
    if "request" in event and "data" in event["request"]:
        data = event["request"]["data"]
        if isinstance(data, dict) and "contract_text" in data:
            data["contract_text"] = "[REDACTED]"
    return event


app = FastAPI(
    title="Contract Checker API",
    description="AI-powered Japanese contract risk analysis for foreign residents",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - restrict in production
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        [settings.FRONTEND_URL, "http://localhost:5173", "http://localhost:3000"]
        if settings.is_development
        else [settings.FRONTEND_URL]
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(upload.router)
app.include_router(payment.router)
app.include_router(analysis.router)
app.include_router(report.router)
app.include_router(referral.router)
app.include_router(eval.router)
