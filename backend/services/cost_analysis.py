import json
import math
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.order import Order
from backend.models.report import Report
from backend.services.token_estimator import get_price_tiers


DEFAULT_PAYMENT_FEE_RATE = 0.0325
DEFAULT_FIXED_BUFFER_JPY = 30.0
DEFAULT_SAFETY_MULTIPLIER = 2.5


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])

    sorted_values = sorted(values)
    rank = (len(sorted_values) - 1) * p
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return float(sorted_values[lower])
    weight = rank - lower
    return float(
        sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
    )


def summarize_numeric(values: list[float]) -> dict[str, float]:
    if not values:
        return {
            "min": 0.0,
            "max": 0.0,
            "avg": 0.0,
            "p50": 0.0,
            "p80": 0.0,
            "p95": 0.0,
        }
    return {
        "min": round(min(values), 3),
        "max": round(max(values), 3),
        "avg": round(sum(values) / len(values), 3),
        "p50": round(percentile(values, 0.50), 3),
        "p80": round(percentile(values, 0.80), 3),
        "p95": round(percentile(values, 0.95), 3),
    }


def recommend_price_jpy(
    cost_jpy: float,
    payment_fee_rate: float = DEFAULT_PAYMENT_FEE_RATE,
    fixed_buffer_jpy: float = DEFAULT_FIXED_BUFFER_JPY,
    safety_multiplier: float = DEFAULT_SAFETY_MULTIPLIER,
) -> int:
    grossed_up = ((cost_jpy + fixed_buffer_jpy) * safety_multiplier) / (1 - payment_fee_rate)
    return int(math.ceil(grossed_up / 10.0) * 10)


def build_cost_pricing_report(
    samples: list[dict[str, Any]],
    payment_fee_rate: float = DEFAULT_PAYMENT_FEE_RATE,
    fixed_buffer_jpy: float = DEFAULT_FIXED_BUFFER_JPY,
    safety_multiplier: float = DEFAULT_SAFETY_MULTIPLIER,
) -> dict[str, Any]:
    costs = [float(sample["total_cost_jpy"]) for sample in samples]
    summary = summarize_numeric(costs)

    by_input_type: dict[str, list[float]] = {}
    by_quote_mode: dict[str, list[float]] = {}
    by_price_tier: dict[str, list[dict[str, Any]]] = {}

    for sample in samples:
        by_input_type.setdefault(sample["input_type"], []).append(float(sample["total_cost_jpy"]))
        by_quote_mode.setdefault(sample["quote_mode"], []).append(float(sample["total_cost_jpy"]))
        by_price_tier.setdefault(sample["price_tier"], []).append(sample)

    tier_price_lookup = {tier["name"]: tier["price_jpy"] for tier in get_price_tiers()}
    tier_rows = []
    for price_tier, tier_samples in by_price_tier.items():
        tier_costs = [float(sample["total_cost_jpy"]) for sample in tier_samples]
        tier_summary = summarize_numeric(tier_costs)
        current_list_price = tier_price_lookup.get(price_tier, 0)
        recommended_price = recommend_price_jpy(
            tier_summary["p95"],
            payment_fee_rate=payment_fee_rate,
            fixed_buffer_jpy=fixed_buffer_jpy,
            safety_multiplier=safety_multiplier,
        )
        tier_rows.append({
            "price_tier": price_tier,
            "sample_count": len(tier_samples),
            "current_list_price_jpy": current_list_price,
            "current_avg_paid_price_jpy": round(
                sum(float(sample["paid_price_jpy"]) for sample in tier_samples) / len(tier_samples), 3
            ),
            "cost_jpy": tier_summary,
            "recommended_price_jpy": recommended_price,
            "p95_margin_jpy_at_current_price": round(current_list_price - tier_summary["p95"], 3),
            "p95_margin_rate_at_current_price": round(
                ((current_list_price - tier_summary["p95"]) / current_list_price) if current_list_price else 0.0,
                4,
            ),
        })

    return {
        "sample_count": len(samples),
        "payment_fee_rate": payment_fee_rate,
        "fixed_buffer_jpy": fixed_buffer_jpy,
        "safety_multiplier": safety_multiplier,
        "overall_cost_jpy": summary,
        "by_input_type": {
            key: summarize_numeric(values)
            for key, values in sorted(by_input_type.items())
        },
        "by_quote_mode": {
            key: summarize_numeric(values)
            for key, values in sorted(by_quote_mode.items())
        },
        "by_price_tier": sorted(tier_rows, key=lambda row: row["current_list_price_jpy"]),
    }


async def load_cost_samples(db: AsyncSession, limit: int = 200) -> list[dict[str, Any]]:
    result = await db.execute(
        select(Report, Order)
        .join(Order, Report.order_id == Order.id)
        .where(Report.cost_summary.is_not(None))
        .order_by(Report.created_at.desc())
        .limit(limit)
    )

    samples: list[dict[str, Any]] = []
    for report, order in result.all():
        cost_summary = report.cost_summary or {}
        total_cost_jpy = float(cost_summary.get("total_cost_jpy", 0.0) or 0.0)
        samples.append({
            "order_id": str(order.id),
            "input_type": order.input_type,
            "quote_mode": order.quote_mode,
            "estimate_source": order.estimate_source,
            "price_tier": order.price_tier,
            "paid_price_jpy": float(order.price_jpy),
            "total_cost_jpy": total_cost_jpy,
            "high_risk_count": report.high_risk_count,
            "medium_risk_count": report.medium_risk_count,
            "low_risk_count": report.low_risk_count,
            "total_clauses": report.total_clauses,
            "created_at": report.created_at.isoformat(),
        })

    return _append_seed_samples(samples, limit=limit)


def load_seed_cost_samples() -> list[dict[str, Any]]:
    settings = get_settings()
    seed_path = Path(settings.COST_SAMPLE_SEED_FILE)
    if not seed_path.is_absolute():
        seed_path = Path.cwd() / seed_path

    try:
        payload = json.loads(seed_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(payload, list):
        return []
    return [sample for sample in payload if isinstance(sample, dict)]


def summarize_sample_sources(samples: list[dict[str, Any]]) -> dict[str, int]:
    seeded = sum(
        1 for sample in samples if str(sample.get("order_id", "")).startswith("seed-")
    )
    return {
        "database_samples": len(samples) - seeded,
        "seed_samples": seeded,
    }


def _append_seed_samples(
    db_samples: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    settings = get_settings()
    minimum_samples = min(max(settings.COST_SAMPLE_MINIMUM, 0), max(limit, 0))
    if len(db_samples) >= minimum_samples:
        return db_samples[:limit]

    merged = list(db_samples)
    existing_ids = {sample["order_id"] for sample in merged}
    for seed_sample in load_seed_cost_samples():
        if seed_sample.get("order_id") in existing_ids:
            continue
        merged.append(seed_sample)
        existing_ids.add(seed_sample["order_id"])
        if len(merged) >= minimum_samples or len(merged) >= limit:
            break
    return merged[:limit]
