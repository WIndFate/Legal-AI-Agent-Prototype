from backend.services.token_estimator import (
    TOKENS_PER_PAGE,
    calculate_price_from_tokens,
    estimate_page_count_from_tokens,
    estimate_price_from_page_count,
    estimate_tokens_and_price,
    get_pricing_policy,
)


def test_short_text_uses_minimum_price():
    """A short text should be charged the minimum price."""
    text = "第1条（目的）本契約は業務委託について定める。" * 10
    result = estimate_tokens_and_price(text)
    assert result["pricing_model"] == "token_linear"
    assert result["price_jpy"] == 200
    assert result["page_estimate"] >= 1
    assert result["estimated_tokens"] > 0


def test_linear_price_rounds_up_by_token_count():
    text = "労働者は、使用者の指揮命令に従い、誠実に業務を遂行しなければならない。" * 320
    result = estimate_tokens_and_price(text)
    assert result["estimated_tokens"] > 1000
    assert result["price_jpy"] == calculate_price_from_tokens(result["estimated_tokens"])


def test_empty_text_returns_minimum_priced_structure():
    result = estimate_tokens_and_price("")
    assert result["estimated_tokens"] == 0
    assert result["page_estimate"] == 1
    assert result["pricing_model"] == "token_linear"
    assert result["price_jpy"] == 200


def test_page_estimate_at_least_one():
    """Page estimate should never be less than 1."""
    assert estimate_page_count_from_tokens(0) >= 1
    assert estimate_page_count_from_tokens(1) >= 1


def test_large_text_scales_linearly():
    text = "甲は乙に対し、本契約に定める業務を委託し、乙はこれを受託する。" * 1000
    result = estimate_tokens_and_price(text)
    assert result["price_jpy"] > 200
    assert result["price_jpy"] == calculate_price_from_tokens(result["estimated_tokens"])


def test_result_has_all_keys():
    """Result dict should contain all required keys."""
    result = estimate_tokens_and_price("テスト")
    assert set(result.keys()) == {"estimated_tokens", "page_estimate", "pricing_model", "price_jpy"}


def test_page_count_fallback_uses_same_linear_pricing():
    result = estimate_price_from_page_count(4)
    assert result["page_estimate"] == 4
    assert result["estimated_tokens"] == 4 * TOKENS_PER_PAGE
    assert result["pricing_model"] == "token_linear"
    assert result["price_jpy"] == calculate_price_from_tokens(4 * TOKENS_PER_PAGE)


def test_runtime_pricing_policy_uses_linear_token_settings():
    policy = get_pricing_policy()
    assert policy["pricing_model"] == "token_linear"
    assert policy["unit_price_jpy_per_1k_tokens"] == 75
    assert policy["minimum_price_jpy"] == 200
