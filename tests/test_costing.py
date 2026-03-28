from types import SimpleNamespace

from backend.services.costing import (
    clear_order_cost_summary,
    estimate_cost_usd,
    get_order_cost_summary,
    log_embedding_usage,
    extract_usage,
    reset_cost_order_context,
    set_cost_order_context,
)


def test_extract_usage_prefers_usage_metadata():
    response = SimpleNamespace(
        usage_metadata={
            "input_tokens": 120,
            "output_tokens": 45,
            "input_token_details": {"cache_read": 20},
        },
        response_metadata={
            "token_usage": {
                "prompt_tokens": 999,
                "completion_tokens": 999,
            }
        },
    )

    usage = extract_usage(response)
    assert usage == {
        "input_tokens": 120,
        "output_tokens": 45,
        "cached_input_tokens": 20,
    }


def test_estimate_cost_usd_accounts_for_cached_tokens():
    cost = estimate_cost_usd(
        "gpt-4o",
        input_tokens=1_000_000,
        output_tokens=100_000,
        cached_input_tokens=200_000,
    )

    expected = (800_000 / 1_000_000) * 2.50 + (200_000 / 1_000_000) * 1.25 + (100_000 / 1_000_000) * 10.00
    assert cost == expected


def test_embedding_usage_updates_order_summary():
    token = set_cost_order_context("order-123")
    try:
        log_embedding_usage(
            "embedding_query",
            "text-embedding-3-small",
            input_tokens=2000,
            item_count=1,
        )
    finally:
        reset_cost_order_context(token)

    summary = get_order_cost_summary("order-123")
    assert summary is not None
    assert summary["step_count"] == 1
    assert summary["total_input_tokens"] == 2000
    assert summary["steps"]["embedding_query"]["calls"] == 1
    assert summary["models"]["text-embedding-3-small"]["calls"] == 1
    assert summary["steps"]["embedding_query"]["models"]["text-embedding-3-small"]["calls"] == 1

    clear_order_cost_summary("order-123")
