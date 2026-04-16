import asyncio
import logging
import subprocess
import time

import asyncpg

from backend.config import get_settings
from backend.db.session import prepare_legacy_schema_for_stamp
from backend.db.url import to_asyncpg_dsn

logger = logging.getLogger(__name__)

LEGACY_BASELINE_REVISION = "009_analysis_job_error_code"
REVISION_ORDER = {
    "001": 1,
    "002": 2,
    "003": 3,
    "004": 4,
    "005": 5,
    "006_analysis_job_cost_summary_and_72h_ttl": 6,
    "007_order_cost_estimates": 7,
    "008_orders_pricing_model": 8,
    "009_analysis_job_error_code": 9,
}


def to_sync_dsn(database_url: str) -> str:
    """Return a sync-compatible PostgreSQL DSN for Alembic/logging helpers."""
    dsn, _ = to_asyncpg_dsn(database_url)
    return dsn


async def wait_for_database(
    dsn: str,
    timeout_seconds: int,
    ssl_value: str | None = None,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    connect_kwargs: dict = {"ssl": ssl_value} if ssl_value else {}

    while time.monotonic() < deadline:
        try:
            conn = await asyncpg.connect(dsn, **connect_kwargs)
            await conn.close()
            return
        except Exception as exc:  # pragma: no cover - network failure path
            last_error = exc
            await asyncio.sleep(1)

    raise RuntimeError(f"Database did not become ready within {timeout_seconds}s") from last_error


async def table_exists(conn: asyncpg.Connection, table_name: str) -> bool:
    return bool(
        await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = $1
            )
            """,
            table_name,
        )
    )


async def has_legacy_bootstrap_tables(conn: asyncpg.Connection) -> bool:
    return await table_exists(conn, "orders")


async def has_alembic_version_table(conn: asyncpg.Connection) -> bool:
    return await table_exists(conn, "alembic_version")


async def column_exists(conn: asyncpg.Connection, table_name: str, column_name: str) -> bool:
    return bool(
        await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = $1
                  AND column_name = $2
            )
            """,
            table_name,
            column_name,
        )
    )


async def read_alembic_revision(conn: asyncpg.Connection) -> str | None:
    if not await has_alembic_version_table(conn):
        return None
    return await conn.fetchval("SELECT version_num FROM alembic_version LIMIT 1")


async def ensure_alembic_version_capacity(conn: asyncpg.Connection) -> None:
    # Some revision IDs (e.g. 006_analysis_job_cost_summary_and_72h_ttl) exceed
    # Alembic's default VARCHAR(32). Pre-create the table at VARCHAR(255) if it's
    # missing, and widen the column if it was left behind by an earlier deploy.
    # Both statements are idempotent so this is safe to run on every boot.
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS public.alembic_version (
            version_num VARCHAR(255) NOT NULL,
            CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
        )
        """
    )
    await conn.execute(
        "ALTER TABLE public.alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)"
    )


async def detect_schema_revision(conn: asyncpg.Connection) -> str | None:
    if await column_exists(conn, "analysis_jobs", "error_code"):
        return "009_analysis_job_error_code"
    if await column_exists(conn, "orders", "pricing_model"):
        return "008_orders_pricing_model"
    if await table_exists(conn, "order_cost_estimates"):
        return "007_order_cost_estimates"
    if await column_exists(conn, "analysis_jobs", "cost_summary"):
        return "006_analysis_job_cost_summary_and_72h_ttl"
    if await table_exists(conn, "analysis_events"):
        return "005"
    if await column_exists(conn, "reports", "cost_summary"):
        return "003"
    if await column_exists(conn, "orders", "quote_mode"):
        return "002"
    if await table_exists(conn, "orders"):
        return "001"
    return None


async def acquire_migration_lock(conn: asyncpg.Connection, lock_id: int) -> None:
    while True:
        acquired = await conn.fetchval("SELECT pg_try_advisory_lock($1)", lock_id)
        if acquired:
            return
        logger.info("Waiting for migration lock %s...", lock_id)
        await asyncio.sleep(1)


async def release_migration_lock(conn: asyncpg.Connection, lock_id: int) -> None:
    await conn.execute("SELECT pg_advisory_unlock($1)", lock_id)


def run_alembic(*args: str) -> None:
    command = ["alembic", *args]
    logger.info("Running migration command: %s", " ".join(command))
    subprocess.run(command, check=True)


async def enforce_rls_on_public_tables(conn: asyncpg.Connection) -> None:
    """Defense-in-depth: ENABLE + FORCE row-level security on every public table.

    Supabase exposes the public schema to PostgREST / GraphQL via the anon JWT
    by default. We already close that door at the Supabase project level
    (public removed from Exposed schemas, pg_graphql disabled, legacy JWT
    keys revoked), but a single misconfiguration could re-open it. Keeping
    RLS forced on every table is the fourth line of defense so a newly added
    table without an explicit policy cannot be read by anon/authenticated
    even if the upstream API surface is accidentally re-enabled.

    Idempotent — safe to run on every boot. Skips alembic_version since it is
    migration metadata, not user data, and alembic needs unrestricted access
    to it. Background: docs/PRE_LAUNCH_AUDIT.md appendix D, INC-2026-04-13.
    """
    await conn.execute(
        """
        DO $$
        DECLARE r record;
        BEGIN
          FOR r IN
            SELECT schemaname, tablename
            FROM pg_tables
            WHERE schemaname = 'public'
              AND tablename  <> 'alembic_version'
          LOOP
            EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY;', r.schemaname, r.tablename);
            EXECUTE format('ALTER TABLE %I.%I FORCE  ROW LEVEL SECURITY;', r.schemaname, r.tablename);
          END LOOP;
        END $$;
        """
    )


async def run_startup_migrations() -> None:
    settings = get_settings()
    dsn, ssl_value = to_asyncpg_dsn(settings.DATABASE_URL)
    connect_kwargs: dict = {"ssl": ssl_value} if ssl_value else {}

    await wait_for_database(dsn, settings.DB_STARTUP_TIMEOUT_SECONDS, ssl_value)

    conn = await asyncpg.connect(dsn, **connect_kwargs)
    try:
        await acquire_migration_lock(conn, settings.MIGRATION_LOCK_ID)
        await ensure_alembic_version_capacity(conn)

        current_revision = await read_alembic_revision(conn)
        detected_revision = await detect_schema_revision(conn)
        current_rank = REVISION_ORDER.get(current_revision or "", 0)
        detected_rank = REVISION_ORDER.get(detected_revision or "", 0)

        if detected_revision and detected_rank > current_rank and await has_legacy_bootstrap_tables(conn):
            logger.warning(
                "Detected schema ahead of alembic revision (%s -> %s); "
                "repairing additive fields and stamping before upgrade.",
                current_revision or "none",
                detected_revision,
            )
            await prepare_legacy_schema_for_stamp()
            run_alembic("stamp", detected_revision)

        run_alembic("upgrade", "head")

        # Defense-in-depth: force RLS on every public table after migrations.
        # Failure here must not block startup — primary protection is at the
        # Supabase project level (public not exposed, pg_graphql off).
        try:
            await enforce_rls_on_public_tables(conn)
            # Emit at WARNING so it surfaces in default log config — this hook is
            # a security control, we want every boot's audit trail to show it ran.
            logger.warning("RLS forced on all public tables (post-migration hook).")
        except Exception as exc:
            logger.warning("RLS enforcement hook failed: %s", exc)
    finally:
        try:
            await release_migration_lock(conn, settings.MIGRATION_LOCK_ID)
        finally:
            await conn.close()

