from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import get_settings
from backend.models.base import Base
from backend.db.url import split_database_ssl_settings, sqlalchemy_connect_args

_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        database_url, _ = split_database_ssl_settings(settings.DATABASE_URL)
        _engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            connect_args=sqlalchemy_connect_args(settings.DATABASE_URL),
        )
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)
    return _session_factory


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields a database session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def prepare_legacy_schema_for_stamp() -> None:
    """Bring legacy create_all-style databases up to the current additive schema before stamping."""
    import backend.models  # noqa: F401 - register SQLAlchemy models

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(
            text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS quote_mode VARCHAR(32) NOT NULL DEFAULT 'exact'")
        )
        await conn.execute(
            text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS estimate_source VARCHAR(32) NOT NULL DEFAULT 'raw_text'")
        )
        await conn.execute(
            text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS pricing_model VARCHAR(32) NOT NULL DEFAULT 'token_linear'")
        )
        await conn.execute(
            text(
                "UPDATE orders SET pricing_model = 'token_linear' "
                "WHERE pricing_model IS NULL OR pricing_model = ''"
            )
        )
        await conn.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS cost_summary JSONB"))
        await conn.execute(text("ALTER TABLE analysis_jobs ADD COLUMN IF NOT EXISTS cost_summary JSONB"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_orders_email ON orders (email)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_orders_payment_status ON orders (payment_status)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_reports_expires_at ON reports (expires_at)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_orders_analysis_status ON orders (analysis_status)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_analysis_jobs_status ON analysis_jobs (status)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_analysis_events_job_id ON analysis_events (job_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_order_cost_estimates_order_id ON order_cost_estimates (order_id)"))
