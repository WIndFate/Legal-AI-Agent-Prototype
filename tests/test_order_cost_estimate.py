from types import SimpleNamespace

from backend.services.order_cost_estimate import (
    build_order_cost_actual_snapshot,
    build_order_cost_comparison_snapshot,
    build_order_cost_estimate_snapshot,
)


def _fake_order(**overrides):
    payload = {
        "id": "order-123",
        "input_type": "pdf",
        "quote_mode": "estimated_pre_ocr",
        "estimate_source": "local_ocr",
        "target_language": "zh-CN",
        "estimated_tokens": 8000,
        "page_estimate": 6,
        "price_jpy": 799,
        "price_tier": "detailed",
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_build_order_cost_estimate_snapshot_includes_model_plan_and_breakdown():
    order = _fake_order()

    snapshot = build_order_cost_estimate_snapshot(order)

    assert snapshot["estimate_version"]
    assert snapshot["pricing_policy_version"]
    assert snapshot["quoted_price_jpy"] == 799
    assert snapshot["predicted_total_cost_jpy"] > 0
    assert snapshot["predicted_clause_count"] > 0
    assert snapshot["model_plan"]["analysis_model"]
    assert "ocr_formal" in snapshot["predicted_cost_breakdown"]
    assert snapshot["predicted_cost_breakdown"]["analyze_clause"]["calls"] == snapshot["predicted_clause_count"]


def test_build_actual_and_comparison_snapshots_capture_model_breakdown():
    order = _fake_order(input_type="text", quote_mode="exact", estimate_source="raw_text")
    cost_summary = {
        "total_cost_usd": 0.02,
        "total_cost_jpy": 3.0,
        "total_input_tokens": 1500,
        "total_output_tokens": 500,
        "steps": {
            "parse_contract": {
                "calls": 1,
                "cost_usd": 0.001,
                "cost_jpy": 0.15,
                "input_tokens": 500,
                "output_tokens": 180,
                "cached_input_tokens": 0,
                "models": {"gpt-4o-mini": {"calls": 1, "cost_usd": 0.001, "cost_jpy": 0.15}},
            },
            "analyze_clause": {
                "calls": 3,
                "cost_usd": 0.012,
                "cost_jpy": 1.8,
                "input_tokens": 700,
                "output_tokens": 210,
                "cached_input_tokens": 0,
                "models": {"gpt-4o": {"calls": 3, "cost_usd": 0.012, "cost_jpy": 1.8}},
            },
            "translate_report": {
                "calls": 1,
                "cost_usd": 0.002,
                "cost_jpy": 0.3,
                "input_tokens": 300,
                "output_tokens": 110,
                "cached_input_tokens": 0,
                "models": {"gpt-4o-mini": {"calls": 1, "cost_usd": 0.002, "cost_jpy": 0.3}},
            },
        },
        "models": {
            "gpt-4o": {"calls": 3, "cost_usd": 0.012, "cost_jpy": 1.8},
            "gpt-4o-mini": {"calls": 2, "cost_usd": 0.003, "cost_jpy": 0.45},
        },
    }
    report_data = {
        "total_clauses": 3,
        "high_risk_count": 1,
        "medium_risk_count": 1,
        "low_risk_count": 1,
    }

    estimate_snapshot = build_order_cost_estimate_snapshot(order)
    actual_snapshot = build_order_cost_actual_snapshot(order, cost_summary, report_data)
    comparison_snapshot = build_order_cost_comparison_snapshot(estimate_snapshot, actual_snapshot)

    assert actual_snapshot is not None
    assert actual_snapshot["actual_model_breakdown"]["gpt-4o"]["calls"] == 3
    assert actual_snapshot["model_plan"]["analysis_model"] == "gpt-4o"
    assert comparison_snapshot is not None
    assert "cost_delta_jpy" in comparison_snapshot
