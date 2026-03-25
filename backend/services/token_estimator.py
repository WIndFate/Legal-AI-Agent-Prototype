import tiktoken

# Price tiers based on estimated page count
PRICE_TIERS = [
    {"name": "basic", "max_pages": 2, "price_jpy": 299},
    {"name": "standard", "max_pages": 5, "price_jpy": 499},
    {"name": "detailed", "max_pages": 10, "price_jpy": 799},
    {"name": "complex", "max_pages": 999, "price_jpy": 1299},
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
    tier = PRICE_TIERS[-1]
    for t in PRICE_TIERS:
        if pages <= t["max_pages"]:
            tier = t
            break
    return tier
