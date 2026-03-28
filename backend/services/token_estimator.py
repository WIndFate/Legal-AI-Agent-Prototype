import json
import math
from functools import lru_cache
from pathlib import Path

import tiktoken

from backend.config import get_settings

DEFAULT_PRICING_POLICY = {
    "pricing_model": "token_linear",
    "unit_price_jpy_per_1k_tokens": 75,
    "minimum_price_jpy": 200,
    "tokens_per_page": 1500,
}

# Roughly 1 page of Japanese contract ≈ 1500 tokens
TOKENS_PER_PAGE = 1500


def estimate_tokens_and_price(text: str) -> dict:
    """Estimate token count, derive an internal page estimate, and compute price."""
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = len(enc.encode(text))
    pages = estimate_page_count_from_tokens(tokens)

    return {
        "estimated_tokens": tokens,
        "page_estimate": pages,
        "pricing_model": get_pricing_policy()["pricing_model"],
        "price_jpy": calculate_price_from_tokens(tokens),
    }


def estimate_price_from_page_count(page_count: int) -> dict:
    """Fallback pricing when only the page count is available."""
    pages = max(1, page_count)
    estimated_tokens = pages * TOKENS_PER_PAGE
    return {
        "estimated_tokens": estimated_tokens,
        "page_estimate": pages,
        "pricing_model": get_pricing_policy()["pricing_model"],
        "price_jpy": calculate_price_from_tokens(estimated_tokens),
    }


def estimate_page_count_from_tokens(tokens: int) -> int:
    return max(1, (max(tokens, 0) + TOKENS_PER_PAGE - 1) // TOKENS_PER_PAGE)


@lru_cache(maxsize=1)
def get_pricing_policy() -> dict[str, int | str]:
    settings = get_settings()
    policy_path = Path(settings.PRICING_POLICY_FILE)
    if not policy_path.is_absolute():
        policy_path = Path.cwd() / policy_path

    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
        if _policy_is_valid(payload):
            return payload
    except (OSError, json.JSONDecodeError):
        pass

    return DEFAULT_PRICING_POLICY


def calculate_price_from_tokens(tokens: int) -> int:
    policy = get_pricing_policy()
    minimum_price_jpy = int(policy["minimum_price_jpy"])
    if tokens <= 0:
        return minimum_price_jpy

    unit_price_jpy_per_1k_tokens = float(policy["unit_price_jpy_per_1k_tokens"])
    linear_price = math.ceil((tokens / 1000.0) * unit_price_jpy_per_1k_tokens)
    return max(minimum_price_jpy, int(linear_price))


def get_pricing_policy_metadata() -> dict[str, str | None]:
    policy = get_pricing_policy()
    settings = get_settings()
    policy_path = Path(settings.PRICING_POLICY_FILE)
    if not policy_path.is_absolute():
        policy_path = Path.cwd() / policy_path

    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "version": None,
            "source": None,
            "pricing_model": str(policy.get("pricing_model")),
            "unit_price_jpy_per_1k_tokens": str(policy.get("unit_price_jpy_per_1k_tokens")),
            "minimum_price_jpy": str(policy.get("minimum_price_jpy")),
        }

    return {
        "version": payload.get("version"),
        "source": payload.get("source"),
        "pricing_model": payload.get("pricing_model"),
        "unit_price_jpy_per_1k_tokens": str(payload.get("unit_price_jpy_per_1k_tokens")),
        "minimum_price_jpy": str(payload.get("minimum_price_jpy")),
    }


def _policy_is_valid(payload: dict) -> bool:
    if not isinstance(payload, dict):
        return False
    return (
        payload.get("pricing_model") == "token_linear"
        and isinstance(payload.get("unit_price_jpy_per_1k_tokens"), (int, float))
        and float(payload["unit_price_jpy_per_1k_tokens"]) > 0
        and isinstance(payload.get("minimum_price_jpy"), int)
        and int(payload["minimum_price_jpy"]) > 0
    )
