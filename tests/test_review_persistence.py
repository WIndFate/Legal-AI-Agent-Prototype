from datetime import datetime

import pytest

from backend.services.report_persistence import save_report


class _FakeDB:
    def __init__(self):
        self.added = []
        self.commit_count = 0

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commit_count += 1


@pytest.mark.asyncio
async def test_save_report_persists_cost_summary():
    db = _FakeDB()
    report_data = {
        "overall_risk_level": "中",
        "summary": "summary",
        "clause_analyses": [],
        "high_risk_count": 0,
        "medium_risk_count": 1,
        "low_risk_count": 0,
        "total_clauses": 1,
    }
    cost_summary = {
        "order_id": "order-1",
        "total_cost_jpy": 1.23,
        "steps": {"analyze_clause": {"calls": 1}},
    }

    payload = await save_report(
        "00000000-0000-0000-0000-000000000001",
        report_data,
        "ja",
        db,
        cost_summary=cost_summary,
    )

    assert db.commit_count == 1
    assert len(db.added) == 1
    assert db.added[0].cost_summary == cost_summary
    assert payload["report"]["overall_risk_level"] == "中"


@pytest.mark.asyncio
async def test_save_report_sets_72_hour_expiry():
    db = _FakeDB()
    payload = await save_report(
        "00000000-0000-0000-0000-000000000002",
        {
            "overall_risk_level": "低",
            "summary": "summary",
            "clause_analyses": [],
            "high_risk_count": 0,
            "medium_risk_count": 0,
            "low_risk_count": 1,
            "total_clauses": 1,
        },
        "ja",
        db,
    )

    created_at = datetime.fromisoformat(payload["created_at"])
    expires_at = datetime.fromisoformat(payload["expires_at"])
    ttl_hours = (expires_at - created_at).total_seconds() / 3600

    assert ttl_hours == pytest.approx(72, abs=0.01)
