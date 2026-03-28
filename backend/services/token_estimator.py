import json
from functools import lru_cache
from pathlib import Path

import tiktoken

from backend.config import get_settings

# Price tiers based on estimated page count.
DEFAULT_PRICE_TIERS = [
    {"name": "basic", "max_pages": 2, "price_jpy": 299},
    {"name": "standard", "max_pages": 5, "price_jpy": 499},
    {"name": "detailed", "max_pages": 10, "price_jpy": 799},
    {"name": "complex", "max_pages": 30, "price_jpy": 1599},
]

# Roughly 1 page of Japanese contract ≈ 1500 tokens
TOKENS_PER_PAGE = 1500


def estimate_tokens_and_price(text: str) -> dict:
    """Estimate token count using tiktoken, derive page estimate, return price tier."""
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = len(enc.encode(text))
    pages = max(1, (tokens + TOKENS_PER_PAGE - 1) // TOKENS_PER_PAGE)
    tier = _tier_for_pages(pages)

    return {
        "estimated_tokens": tokens,
        "page_estimate": pages,
        "price_tier": tier["name"],
        "price_jpy": tier["price_jpy"],
    }

def estimate_price_from_page_count(page_count: int) -> dict:
    """Fallback pricing when only the page count is available."""
    pages = max(1, page_count)
    tier = _tier_for_pages(pages)
    return {
        "estimated_tokens": pages * TOKENS_PER_PAGE,
        "page_estimate": pages,
        "price_tier": tier["name"],
        "price_jpy": tier["price_jpy"],
    }


def _tier_for_pages(pages: int) -> dict:
    price_tiers = get_price_tiers()
    tier = price_tiers[-1]
    for t in price_tiers:
        if pages <= t["max_pages"]:
            tier = t
            break
    return tier


@lru_cache(maxsize=1)
def get_price_tiers() -> list[dict]:
    settings = get_settings()
    policy_path = Path(settings.PRICING_POLICY_FILE)
    if not policy_path.is_absolute():
        policy_path = Path.cwd() / policy_path

    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
        tiers = payload.get("tiers", [])
        if _tiers_are_valid(tiers):
            return tiers
    except (OSError, json.JSONDecodeError):
        pass

    return DEFAULT_PRICE_TIERS


def get_pricing_policy_metadata() -> dict[str, str | None]:
    settings = get_settings()
    policy_path = Path(settings.PRICING_POLICY_FILE)
    if not policy_path.is_absolute():
        policy_path = Path.cwd() / policy_path

    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": None, "source": None}

    return {
        "version": payload.get("version"),
        "source": payload.get("source"),
    }


def _tiers_are_valid(tiers: list[dict]) -> bool:
    if not tiers:
        return False
    required_names = {"basic", "standard", "detailed", "complex"}
    names = {tier.get("name") for tier in tiers}
    if names != required_names:
        return False
    return all(
        isinstance(tier.get("max_pages"), int)
        and tier["max_pages"] > 0
        and isinstance(tier.get("price_jpy"), int)
        and tier["price_jpy"] > 0
        for tier in tiers
    )
