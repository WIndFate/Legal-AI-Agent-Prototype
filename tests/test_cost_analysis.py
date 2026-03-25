import pytest

from backend.services.cost_analysis import (
    build_cost_pricing_report,
    load_seed_cost_samples,
    percentile,
    recommend_price_jpy,
    summarize_sample_sources,
)
from backend.services.token_estimator import get_price_tiers


def test_percentile_interpolates_sorted_values():
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.95) == pytest.approx(3.85)


def test_recommend_price_jpy_rounds_up_with_buffer_and_fee():
    recommended = recommend_price_jpy(100.0, payment_fee_rate=0.0325, fixed_buffer_jpy=30.0, safety_multiplier=2.5)
    assert recommended == 340


def test_build_cost_pricing_report_groups_by_tier_and_input_type():
    samples = [
        {
            "order_id": "a",
            "input_type": "text",
            "quote_mode": "exact",
            "estimate_source": "raw_text",
            "price_tier": "basic",
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
            "quote_mode": "estimated_pre_ocr",
            "estimate_source": "local_ocr",
            "price_tier": "standard",
            "paid_price_jpy": 499.0,
            "total_cost_jpy": 12.0,
            "high_risk_count": 1,
            "medium_risk_count": 1,
            "low_risk_count": 1,
            "total_clauses": 3,
            "created_at": "2026-03-26T00:00:00+00:00",
        },
    ]

    report = build_cost_pricing_report(samples, fixed_buffer_jpy=30.0, safety_multiplier=2.5)

    assert report["sample_count"] == 2
    assert report["by_input_type"]["text"]["avg"] == 1.4
    assert report["by_input_type"]["pdf"]["avg"] == 12.0
    assert report["by_quote_mode"]["estimated_pre_ocr"]["avg"] == 12.0
    assert len(report["by_price_tier"]) == 2
    assert report["by_price_tier"][0]["price_tier"] == "basic"
    assert report["by_price_tier"][1]["price_tier"] == "standard"


def test_seed_cost_samples_cover_all_four_price_tiers():
    samples = load_seed_cost_samples()
    tiers = {sample["price_tier"] for sample in samples}
    assert len(samples) >= 10
    assert tiers == {"basic", "standard", "detailed", "complex"}


def test_runtime_price_tiers_use_policy_file():
    tiers = get_price_tiers()
    assert tiers[-1]["name"] == "complex"
    assert tiers[-1]["price_jpy"] == 1599
    assert tiers[-1]["max_pages"] == 30


def test_summarize_sample_sources_counts_seed_vs_database_rows():
    result = summarize_sample_sources([
        {"order_id": "seed-basic-text-001"},
        {"order_id": "real-order-123"},
    ])
    assert result == {"database_samples": 1, "seed_samples": 1}
