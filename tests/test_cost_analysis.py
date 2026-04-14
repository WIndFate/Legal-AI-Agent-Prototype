import pytest

from backend.services.cost_analysis import (
    build_cost_pricing_report,
    load_seed_cost_samples,
    percentile,
    recommend_price_jpy,
    summarize_sample_sources,
)
from backend.services.token_estimator import get_pricing_policy


def test_percentile_interpolates_sorted_values():
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.95) == pytest.approx(3.85)


def test_recommend_price_jpy_rounds_up_with_buffer_and_fee():
    recommended = recommend_price_jpy(100.0, payment_fee_rate=0.0325, fixed_buffer_jpy=30.0, safety_multiplier=2.5)
    assert recommended == 340


def test_recommend_price_jpy_includes_target_margin_rate():
    recommended = recommend_price_jpy(
        100.0,
        payment_fee_rate=0.0325,
        fixed_buffer_jpy=30.0,
        safety_multiplier=2.5,
        target_margin_rate=0.75,
    )
    assert recommended == 1500


def test_build_cost_pricing_report_groups_by_pricing_model_and_input_type():
    samples = [
        {
            "order_id": "a",
            "input_type": "text",
            "quote_mode": "exact",
            "estimate_source": "raw_text",
            "pricing_model": "token_linear",
            "paid_price_band": "200-399",
            "paid_price_jpy": 299.0,
            "total_cost_jpy": 1.4,
            "high_risk_count": 0,
            "medium_risk_count": 2,
            "low_risk_count": 0,
            "total_clauses": 2,
            "created_at": "2026-03-26T00:00:00+00:00",
        },
        {
            "order_id": "b",
            "input_type": "pdf",
            "quote_mode": "exact",
            "estimate_source": "vision_ocr",
            "pricing_model": "token_linear",
            "paid_price_band": "400-599",
            "paid_price_jpy": 499.0,
            "total_cost_jpy": 12.0,
            "high_risk_count": 1,
            "medium_risk_count": 1,
            "low_risk_count": 1,
            "total_clauses": 3,
            "created_at": "2026-03-26T00:00:00+00:00",
        },
    ]

    report = build_cost_pricing_report(
        samples,
        fixed_buffer_jpy=30.0,
        safety_multiplier=2.5,
        target_margin_rate=0.75,
    )

    assert report["sample_count"] == 2
    assert report["target_margin_rate"] == 0.75
    assert report["by_input_type"]["text"]["avg"] == 1.4
    assert report["by_input_type"]["pdf"]["avg"] == 12.0
    assert report["by_quote_mode"]["exact"]["avg"] == pytest.approx((1.4 + 12.0) / 2, rel=0, abs=0.001)
    assert report["by_pricing_model"]["token_linear"]["sample_count"] == 2
    assert report["by_paid_price_band"]["200-399"]["sample_count"] == 1
    assert report["by_pricing_recommendation"][0]["pricing_model"] == "token_linear"
    assert report["by_pricing_recommendation"][0]["recommended_price_jpy_cost_floor"] > 0
    assert (
        report["by_pricing_recommendation"][0]["recommended_price_jpy_target_margin"]
        > report["by_pricing_recommendation"][0]["recommended_price_jpy_cost_floor"]
    )


def test_seed_cost_samples_use_token_linear_pricing():
    samples = load_seed_cost_samples()
    assert len(samples) >= 10
    assert {sample["pricing_model"] for sample in samples} == {"token_linear"}


def test_runtime_pricing_policy_uses_linear_token_file():
    policy = get_pricing_policy()
    assert policy["pricing_model"] == "token_linear"
    assert policy["unit_price_jpy_per_1k_tokens"] == 75
    assert policy["minimum_price_jpy"] == 200


def test_summarize_sample_sources_counts_seed_vs_database_rows():
    result = summarize_sample_sources([
        {"order_id": "seed-basic-text-001"},
        {"order_id": "real-order-123"},
    ])
    assert result == {"database_samples": 1, "seed_samples": 1}
