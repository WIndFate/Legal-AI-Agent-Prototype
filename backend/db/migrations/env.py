import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from backend.config import get_settings
from backend.db.url import split_database_ssl_settings, sqlalchemy_connect_args
from backend.models.base import Base

# Import all models so they register with Base.metadata
from backend.models import analysis_event, analysis_job, order, order_cost_estimate, referral, report  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    database_url, _ = split_database_ssl_settings(get_settings().DATABASE_URL)
    return database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Some revision IDs (e.g. 006_analysis_job_cost_summary_and_72h_ttl) exceed
        # Alembic's default VARCHAR(32). Match ensure_alembic_version_capacity so
        # fresh databases create the column wide enough on first upgrade.
        version_table_column_length=255,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_column_length=255,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    settings = get_settings()
    connectable = create_async_engine(
        get_url(),
        pool_pre_ping=True,
        connect_args=sqlalchemy_connect_args(settings.DATABASE_URL),
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
