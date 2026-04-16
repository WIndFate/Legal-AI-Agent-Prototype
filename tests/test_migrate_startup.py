import pytest

from backend.db.migrate_startup import (
    REVISION_ORDER,
    enforce_rls_on_public_tables,
    to_sync_dsn,
)


def test_to_sync_dsn_strips_asyncpg_driver():
    assert (
        to_sync_dsn("postgresql+asyncpg://postgres:postgres@postgres:5432/contract_checker")
        == "postgresql://postgres:postgres@postgres:5432/contract_checker"
    )


def test_revision_order_tracks_latest_cost_estimate_revision():
    assert REVISION_ORDER["008_orders_pricing_model"] > REVISION_ORDER["007_order_cost_estimates"]


class _CapturingConn:
    def __init__(self):
        self.executed: list[str] = []

    async def execute(self, sql: str) -> None:
        self.executed.append(sql)


@pytest.mark.asyncio
async def test_enforce_rls_on_public_tables_skips_alembic_version_and_forces_rls():
    """Hook must skip alembic_version and emit ENABLE + FORCE on every other table."""
    conn = _CapturingConn()
    await enforce_rls_on_public_tables(conn)
    assert len(conn.executed) == 1, "Hook should issue exactly one batched DO block"
    sql = conn.executed[0]
    # Skip migration metadata table (alembic owns it, RLS would break stamping).
    assert "tablename  <> 'alembic_version'" in sql
    # Both ENABLE and FORCE must be issued so anon/authenticated have no path
    # in even if PostgREST/GraphQL are accidentally re-enabled upstream.
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "FORCE  ROW LEVEL SECURITY" in sql
    # Restrict scope to public schema; never touch system schemas like
    # pg_catalog or extensions where forcing RLS would be destructive.
    assert "schemaname = 'public'" in sql
