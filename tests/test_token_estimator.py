from backend.services.token_estimator import estimate_price_from_page_count, estimate_tokens_and_price, TOKENS_PER_PAGE


def test_short_text_basic_tier():
    """A short text (< 2 pages) should be priced as 'basic'."""
    text = "第1条（目的）本契約は業務委託について定める。" * 10
    result = estimate_tokens_and_price(text)
    assert result["price_tier"] == "basic"
    assert result["price_jpy"] == 299
    assert result["page_estimate"] >= 1
    assert result["estimated_tokens"] > 0


def test_medium_text_standard_tier():
    """Text around 3-5 pages should be 'standard'."""
    # ~4500 tokens ≈ 3 pages
    text = "労働者は、使用者の指揮命令に従い、誠実に業務を遂行しなければならない。" * 300
    result = estimate_tokens_and_price(text)
    assert result["price_tier"] in ("standard", "detailed")
    assert result["price_jpy"] in (499, 799)


def test_empty_text_returns_basic():
    """Empty or minimal text should still return valid result at basic tier."""
    result = estimate_tokens_and_price("")
    assert result["estimated_tokens"] == 0
    assert result["page_estimate"] == 1
    assert result["price_tier"] == "basic"
    assert result["price_jpy"] == 299


def test_page_estimate_at_least_one():
    """Page estimate should never be less than 1."""
    result = estimate_tokens_and_price("短い")
    assert result["page_estimate"] >= 1


def test_large_text_complex_tier():
    """Very large text (>10 pages) should be 'complex'."""
    # >15000 tokens ≈ >10 pages
    text = "甲は乙に対し、本契約に定める業務を委託し、乙はこれを受託する。" * 1000
    result = estimate_tokens_and_price(text)
    assert result["price_tier"] == "complex"
    assert result["price_jpy"] == 1299


def test_result_has_all_keys():
    """Result dict should contain all required keys."""
    result = estimate_tokens_and_price("テスト")
    assert set(result.keys()) == {"estimated_tokens", "page_estimate", "price_tier", "price_jpy"}


def test_page_count_fallback_uses_same_pricing_grid():
    result = estimate_price_from_page_count(4)
    assert result["page_estimate"] == 4
    assert result["estimated_tokens"] == 4 * TOKENS_PER_PAGE
    assert result["price_tier"] == "standard"
    assert result["price_jpy"] == 499
