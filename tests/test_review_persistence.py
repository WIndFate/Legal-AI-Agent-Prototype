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
