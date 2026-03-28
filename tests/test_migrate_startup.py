from backend.db.migrate_startup import REVISION_ORDER, to_sync_dsn


def test_to_sync_dsn_strips_asyncpg_driver():
    assert (
        to_sync_dsn("postgresql+asyncpg://postgres:postgres@postgres:5432/contract_checker")
        == "postgresql://postgres:postgres@postgres:5432/contract_checker"
    )


def test_revision_order_tracks_latest_cost_estimate_revision():
    assert REVISION_ORDER["007_order_cost_estimates"] > REVISION_ORDER["005"]
