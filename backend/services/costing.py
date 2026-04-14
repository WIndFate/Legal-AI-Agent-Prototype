import logging
from collections import defaultdict
from contextvars import ContextVar, Token
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

USD_TO_JPY_RATE = 150.0

MODEL_PRICING_USD_PER_1M = {
    "gpt-4o": {"input": 2.50, "output": 10.00, "cached_input": 1.25},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "cached_input": 0.075},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0, "cached_input": 0.0},
}

_current_order_id: ContextVar[str | None] = ContextVar("cost_order_id", default=None)
_order_cost_summaries: dict[str, dict[str, Any]] = {}
_order_cost_lock = Lock()


def set_cost_order_context(order_id: str | None) -> Token:
    """Set the current order id for structured usage logging."""
    return _current_order_id.set(order_id)


def reset_cost_order_context(token: Token) -> None:
    """Restore the previous order id context."""
    _current_order_id.reset(token)


def get_cost_order_context() -> str | None:
    """Return the current order id if one has been bound to this context."""
    return _current_order_id.get()


def extract_usage(response: Any) -> dict[str, int]:
    """Normalize token usage metadata from LangChain/OpenAI responses."""
    usage_metadata = getattr(response, "usage_metadata", None) or {}
    response_metadata = getattr(response, "response_metadata", None) or {}
    token_usage = response_metadata.get("token_usage", {}) if isinstance(response_metadata, dict) else {}
    responses_api_usage = getattr(response, "usage", None)
    responses_input_details = getattr(responses_api_usage, "input_tokens_details", None)

    input_tokens = int(
        usage_metadata.get("input_tokens")
        or token_usage.get("prompt_tokens")
        or getattr(responses_api_usage, "input_tokens", 0)
        or 0
    )
    output_tokens = int(
        usage_metadata.get("output_tokens")
        or token_usage.get("completion_tokens")
        or getattr(responses_api_usage, "output_tokens", 0)
        or 0
    )
    cached_input_tokens = int(
        usage_metadata.get("input_token_details", {}).get("cache_read")
        or token_usage.get("prompt_tokens_details", {}).get("cached_tokens")
        or getattr(responses_input_details, "cached_tokens", 0)
        or 0
    )

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_input_tokens": cached_input_tokens,
    }


def estimate_cost_usd(
    model: str,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_input_tokens: int = 0,
) -> float:
    """Estimate API cost from token usage using a static pricing table."""
    pricing = MODEL_PRICING_USD_PER_1M.get(model)
    if pricing is None:
        return 0.0

    uncached_input_tokens = max(0, input_tokens - cached_input_tokens)
    return (
        (uncached_input_tokens / 1_000_000) * pricing["input"]
        + (cached_input_tokens / 1_000_000) * pricing["cached_input"]
        + (output_tokens / 1_000_000) * pricing["output"]
    )


def estimate_cost_jpy(model: str, **usage: int) -> float:
    """Estimate API cost in JPY from token usage using a static FX assumption."""
    return estimate_cost_usd(model, **usage) * USD_TO_JPY_RATE


def log_model_usage(step_name: str, model: str, response: Any, **extra: Any) -> None:
    """Emit structured usage/cost logs for later cost validation."""
    usage = extract_usage(response)
    cost_usd = estimate_cost_usd(model, **usage)
    cost_jpy = estimate_cost_jpy(model, **usage)
    payload = {
        "order_id": get_cost_order_context(),
        "step_name": step_name,
        "model": model,
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "cached_input_tokens": usage["cached_input_tokens"],
        "estimated_cost_usd": round(cost_usd, 6),
        "estimated_cost_jpy": round(cost_jpy, 3),
        **extra,
    }
    _record_order_cost(payload)
    logger.info("Model usage: %s", payload)


def log_embedding_usage(
    step_name: str,
    model: str,
    *,
    input_tokens: int,
    item_count: int,
    **extra: Any,
) -> None:
    """Emit structured usage/cost logs for embedding requests."""
    cost_usd = estimate_cost_usd(model, input_tokens=input_tokens, output_tokens=0, cached_input_tokens=0)
    cost_jpy = estimate_cost_jpy(model, input_tokens=input_tokens, output_tokens=0, cached_input_tokens=0)
    payload = {
        "order_id": get_cost_order_context(),
        "step_name": step_name,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": 0,
        "cached_input_tokens": 0,
        "estimated_cost_usd": round(cost_usd, 6),
        "estimated_cost_jpy": round(cost_jpy, 3),
        "item_count": item_count,
        **extra,
    }
    _record_order_cost(payload)
    logger.info("Embedding usage: %s", payload)



def get_order_cost_summary(order_id: str) -> dict[str, Any] | None:
    """Return the current in-memory cost summary for an order."""
    with _order_cost_lock:
        summary = _order_cost_summaries.get(order_id)
        if summary is None:
            return None
        return {
            **summary,
            "steps": {
                step_name: {
                    **step_data,
                    "models": dict(step_data["models"]),
                }
                for step_name, step_data in summary["steps"].items()
            },
            "models": dict(summary["models"]),
        }


def clear_order_cost_summary(order_id: str) -> None:
    """Drop the in-memory cost summary once it has been persisted or logged."""
    with _order_cost_lock:
        _order_cost_summaries.pop(order_id, None)


def _record_order_cost(payload: dict[str, Any]) -> None:
    order_id = payload.get("order_id")
    if not order_id:
        return

    with _order_cost_lock:
        summary = _order_cost_summaries.setdefault(
            order_id,
            {
                "order_id": order_id,
                "total_cost_usd": 0.0,
                "total_cost_jpy": 0.0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "step_count": 0,
                "steps": defaultdict(
                    lambda: {
                        "cost_usd": 0.0,
                        "cost_jpy": 0.0,
                        "calls": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "cached_input_tokens": 0,
                        "models": defaultdict(lambda: {"cost_usd": 0.0, "cost_jpy": 0.0, "calls": 0}),
                    }
                ),
                "models": defaultdict(lambda: {"cost_usd": 0.0, "cost_jpy": 0.0, "calls": 0}),
            },
        )
        summary["total_cost_usd"] += float(payload.get("estimated_cost_usd", 0.0))
        summary["total_cost_jpy"] += float(payload.get("estimated_cost_jpy", 0.0))
        summary["total_input_tokens"] += int(payload.get("input_tokens", 0))
        summary["total_output_tokens"] += int(payload.get("output_tokens", 0))
        summary["step_count"] += 1
        step = summary["steps"][payload["step_name"]]
        step["cost_usd"] += float(payload.get("estimated_cost_usd", 0.0))
        step["cost_jpy"] += float(payload.get("estimated_cost_jpy", 0.0))
        step["calls"] += 1
        step["input_tokens"] += int(payload.get("input_tokens", 0))
        step["output_tokens"] += int(payload.get("output_tokens", 0))
        step["cached_input_tokens"] += int(payload.get("cached_input_tokens", 0))
        model_name = str(payload.get("model") or "")
        if model_name:
            model = summary["models"][model_name]
            model["cost_usd"] += float(payload.get("estimated_cost_usd", 0.0))
            model["cost_jpy"] += float(payload.get("estimated_cost_jpy", 0.0))
            model["calls"] += 1
            step_model = step["models"][model_name]
            step_model["cost_usd"] += float(payload.get("estimated_cost_usd", 0.0))
            step_model["cost_jpy"] += float(payload.get("estimated_cost_jpy", 0.0))
            step_model["calls"] += 1
