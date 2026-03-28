import json
import math
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.order import Order
from backend.models.order_cost_estimate import OrderCostEstimate
from backend.models.report import Report


DEFAULT_PAYMENT_FEE_RATE = 0.0325
DEFAULT_FIXED_BUFFER_JPY = 30.0
DEFAULT_SAFETY_MULTIPLIER = 2.5
DEFAULT_TARGET_MARGIN_RATE = 0.75


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
    target_margin_rate: float = 0.0,
) -> int:
    denominator = 1 - payment_fee_rate - target_margin_rate
    if denominator <= 0:
        raise ValueError("payment_fee_rate + target_margin_rate must be < 1.0")
    grossed_up = ((cost_jpy + fixed_buffer_jpy) * safety_multiplier) / denominator
    return int(math.ceil(grossed_up / 10.0) * 10)


def build_cost_pricing_report(
    samples: list[dict[str, Any]],
    payment_fee_rate: float = DEFAULT_PAYMENT_FEE_RATE,
    fixed_buffer_jpy: float = DEFAULT_FIXED_BUFFER_JPY,
    safety_multiplier: float = DEFAULT_SAFETY_MULTIPLIER,
    target_margin_rate: float = DEFAULT_TARGET_MARGIN_RATE,
) -> dict[str, Any]:
    costs = [float(sample["total_cost_jpy"]) for sample in samples]
    summary = summarize_numeric(costs)

    by_input_type: dict[str, list[float]] = {}
    by_quote_mode: dict[str, list[float]] = {}
    by_pricing_model: dict[str, list[dict[str, Any]]] = {}
    by_paid_price_band: dict[str, list[dict[str, Any]]] = {}
    by_estimate_version: dict[str, list[dict[str, Any]]] = {}
    by_model_signature: dict[str, list[dict[str, Any]]] = {}
    estimate_cost_deltas: list[float] = []
    estimate_margin_deltas: list[float] = []

    for sample in samples:
        by_input_type.setdefault(sample["input_type"], []).append(float(sample["total_cost_jpy"]))
        by_quote_mode.setdefault(sample["quote_mode"], []).append(float(sample["total_cost_jpy"]))
        by_pricing_model.setdefault(str(sample.get("pricing_model") or "unknown"), []).append(sample)
        by_paid_price_band.setdefault(_price_band_label(float(sample["paid_price_jpy"])), []).append(sample)
        if sample.get("estimate_version"):
            by_estimate_version.setdefault(str(sample["estimate_version"]), []).append(sample)
        if sample.get("model_signature"):
            by_model_signature.setdefault(str(sample["model_signature"]), []).append(sample)
        if sample.get("estimate_vs_actual_cost_delta_jpy") is not None:
            estimate_cost_deltas.append(float(sample["estimate_vs_actual_cost_delta_jpy"]))
        if sample.get("estimate_vs_actual_margin_delta_jpy") is not None:
            estimate_margin_deltas.append(float(sample["estimate_vs_actual_margin_delta_jpy"]))

    pricing_rows = []
    for pricing_model, pricing_samples in by_pricing_model.items():
        model_costs = [float(sample["total_cost_jpy"]) for sample in pricing_samples]
        model_summary = summarize_numeric(model_costs)
        current_avg_price = round(
            sum(float(sample["paid_price_jpy"]) for sample in pricing_samples) / len(pricing_samples),
            3,
        )
        cost_floor_price = recommend_price_jpy(
            model_summary["p95"],
            payment_fee_rate=payment_fee_rate,
            fixed_buffer_jpy=fixed_buffer_jpy,
            safety_multiplier=safety_multiplier,
        )
        target_margin_price = recommend_price_jpy(
            model_summary["p95"],
            payment_fee_rate=payment_fee_rate,
            fixed_buffer_jpy=fixed_buffer_jpy,
            safety_multiplier=safety_multiplier,
            target_margin_rate=target_margin_rate,
        )
        adjusted_p95_cost = round(
            (model_summary["p95"] + fixed_buffer_jpy) * safety_multiplier,
            3,
        )
        effective_margin_rate = 0.0
        if current_avg_price:
            effective_margin_rate = round(
                (
                    current_avg_price * (1 - payment_fee_rate) - adjusted_p95_cost
                ) / current_avg_price,
                4,
            )
        pricing_rows.append({
            "pricing_model": pricing_model,
            "sample_count": len(pricing_samples),
            "current_avg_paid_price_jpy": current_avg_price,
            "cost_jpy": model_summary,
            "adjusted_p95_cost_jpy": adjusted_p95_cost,
            "recommended_price_jpy_cost_floor": cost_floor_price,
            "recommended_price_jpy_target_margin": target_margin_price,
            "p95_margin_jpy_at_current_price": round(current_avg_price - model_summary["p95"], 3),
            "p95_margin_rate_at_current_price": round(
                ((current_avg_price - model_summary["p95"]) / current_avg_price) if current_avg_price else 0.0,
                4,
            ),
            "effective_margin_rate_after_fee_and_buffers": effective_margin_rate,
        })

    return {
        "sample_count": len(samples),
        "payment_fee_rate": payment_fee_rate,
        "fixed_buffer_jpy": fixed_buffer_jpy,
        "safety_multiplier": safety_multiplier,
        "target_margin_rate": target_margin_rate,
        "overall_cost_jpy": summary,
        "estimate_vs_actual_cost_delta_jpy": summarize_numeric(estimate_cost_deltas),
        "estimate_vs_actual_margin_delta_jpy": summarize_numeric(estimate_margin_deltas),
        "by_input_type": {
            key: summarize_numeric(values)
            for key, values in sorted(by_input_type.items())
        },
        "by_quote_mode": {
            key: summarize_numeric(values)
            for key, values in sorted(by_quote_mode.items())
        },
        "by_pricing_model": {
            key: {
                "sample_count": len(value),
                "cost_jpy": summarize_numeric([float(sample["total_cost_jpy"]) for sample in value]),
                "avg_paid_price_jpy": round(
                    sum(float(sample["paid_price_jpy"]) for sample in value) / len(value),
                    3,
                ),
            }
            for key, value in sorted(by_pricing_model.items())
        },
        "by_paid_price_band": {
            key: {
                "sample_count": len(value),
                "cost_jpy": summarize_numeric([float(sample["total_cost_jpy"]) for sample in value]),
                "avg_paid_price_jpy": round(
                    sum(float(sample["paid_price_jpy"]) for sample in value) / len(value),
                    3,
                ),
            }
            for key, value in sorted(by_paid_price_band.items())
        },
        "by_estimate_version": {
            key: {
                "sample_count": len(value),
                "cost_jpy": summarize_numeric([float(sample["total_cost_jpy"]) for sample in value]),
                "estimate_vs_actual_cost_delta_jpy": summarize_numeric(
                    [
                        float(sample["estimate_vs_actual_cost_delta_jpy"])
                        for sample in value
                        if sample.get("estimate_vs_actual_cost_delta_jpy") is not None
                    ]
                ),
            }
            for key, value in sorted(by_estimate_version.items())
        },
        "by_model_signature": {
            key: {
                "sample_count": len(value),
                "cost_jpy": summarize_numeric([float(sample["total_cost_jpy"]) for sample in value]),
                "estimate_vs_actual_cost_delta_jpy": summarize_numeric(
                    [
                        float(sample["estimate_vs_actual_cost_delta_jpy"])
                        for sample in value
                        if sample.get("estimate_vs_actual_cost_delta_jpy") is not None
                    ]
                ),
            }
            for key, value in sorted(by_model_signature.items())
        },
        "by_pricing_recommendation": sorted(pricing_rows, key=lambda row: row["current_avg_paid_price_jpy"]),
    }


def build_ops_dashboard(
    samples: list[dict[str, Any]],
    *,
    recent_limit: int = 25,
) -> dict[str, Any]:
    actual_costs = [float(sample["total_cost_jpy"]) for sample in samples]
    revenues = [float(sample["paid_price_jpy"]) for sample in samples]
    margins = [float(sample["actual_margin_jpy"]) for sample in samples]
    margin_rates = [float(sample["actual_margin_rate"]) for sample in samples]
    estimate_cost_deltas = [
        float(sample["estimate_vs_actual_cost_delta_jpy"])
        for sample in samples
        if sample.get("estimate_vs_actual_cost_delta_jpy") is not None
    ]
    estimate_margin_deltas = [
        float(sample["estimate_vs_actual_margin_delta_jpy"])
        for sample in samples
        if sample.get("estimate_vs_actual_margin_delta_jpy") is not None
    ]

    def _group(key: str) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for sample in samples:
            grouped.setdefault(str(sample.get(key) or "unknown"), []).append(sample)
        return {
            name: _summarize_ops_group(rows)
            for name, rows in sorted(grouped.items())
        }

    recent_orders = sorted(
        samples,
        key=lambda sample: str(sample.get("created_at") or ""),
        reverse=True,
    )[: max(recent_limit, 0)]

    return {
        "sample_count": len(samples),
        "overall": {
            "revenue_jpy": summarize_numeric(revenues),
            "actual_cost_jpy": summarize_numeric(actual_costs),
            "actual_margin_jpy": summarize_numeric(margins),
            "actual_margin_rate": summarize_numeric(margin_rates),
            "estimate_vs_actual_cost_delta_jpy": summarize_numeric(estimate_cost_deltas),
            "estimate_vs_actual_margin_delta_jpy": summarize_numeric(estimate_margin_deltas),
        },
        "by_pricing_model": _group("pricing_model"),
        "by_paid_price_band": _group("paid_price_band"),
        "by_input_type": _group("input_type"),
        "by_quote_mode": _group("quote_mode"),
        "by_target_language": _group("target_language"),
        "by_estimate_version": _group("estimate_version"),
        "by_model_signature": _group("model_signature"),
        "recent_orders": [
            {
                "order_id": sample["order_id"],
                "created_at": sample["created_at"],
                "input_type": sample["input_type"],
                "quote_mode": sample["quote_mode"],
                "target_language": sample["target_language"],
                "pricing_model": sample["pricing_model"],
                "paid_price_band": sample["paid_price_band"],
                "paid_price_jpy": sample["paid_price_jpy"],
                "predicted_total_cost_jpy": sample["predicted_total_cost_jpy"],
                "actual_total_cost_jpy": sample["total_cost_jpy"],
                "actual_margin_jpy": sample["actual_margin_jpy"],
                "actual_margin_rate": sample["actual_margin_rate"],
                "estimate_vs_actual_cost_delta_jpy": sample["estimate_vs_actual_cost_delta_jpy"],
                "estimate_vs_actual_margin_delta_jpy": sample["estimate_vs_actual_margin_delta_jpy"],
                "estimate_version": sample["estimate_version"],
                "model_signature": sample["model_signature"],
            }
            for sample in recent_orders
        ],
    }


async def load_cost_samples(
    db: AsyncSession,
    limit: int = 200,
    *,
    include_seed: bool = True,
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(Report, Order, OrderCostEstimate)
        .join(Order, Report.order_id == Order.id)
        .outerjoin(OrderCostEstimate, OrderCostEstimate.order_id == Order.id)
        .where(Report.cost_summary.is_not(None))
        .order_by(Report.created_at.desc())
        .limit(limit)
    )

    samples: list[dict[str, Any]] = []
    for report, order, order_cost_estimate in result.all():
        cost_summary = report.cost_summary or {}
        total_cost_jpy = float(cost_summary.get("total_cost_jpy", 0.0) or 0.0)
        estimate_snapshot = (order_cost_estimate.estimate_snapshot if order_cost_estimate else None) or {}
        comparison_snapshot = (order_cost_estimate.comparison_snapshot if order_cost_estimate else None) or {}
        model_plan = estimate_snapshot.get("model_plan") or {}
        samples.append({
            "order_id": str(order.id),
            "input_type": order.input_type,
            "quote_mode": order.quote_mode,
            "estimate_source": order.estimate_source,
            "target_language": order.target_language,
            "pricing_model": estimate_snapshot.get("pricing_model") or order.price_tier,
            "paid_price_band": _price_band_label(float(order.price_jpy)),
            "paid_price_jpy": float(order.price_jpy),
            "total_cost_jpy": total_cost_jpy,
            "actual_margin_jpy": round(float(order.price_jpy) - total_cost_jpy, 3),
            "actual_margin_rate": round(
                ((float(order.price_jpy) - total_cost_jpy) / float(order.price_jpy))
                if float(order.price_jpy)
                else 0.0,
                4,
            ),
            "high_risk_count": report.high_risk_count,
            "medium_risk_count": report.medium_risk_count,
            "low_risk_count": report.low_risk_count,
            "total_clauses": report.total_clauses,
            "estimate_version": estimate_snapshot.get("estimate_version"),
            "pricing_policy_version": estimate_snapshot.get("pricing_policy_version"),
            "predicted_total_cost_jpy": float(estimate_snapshot.get("predicted_total_cost_jpy", 0.0) or 0.0),
            "estimate_vs_actual_cost_delta_jpy": comparison_snapshot.get("cost_delta_jpy"),
            "estimate_vs_actual_margin_delta_jpy": comparison_snapshot.get("margin_delta_jpy"),
            "model_signature": _build_model_signature(model_plan),
            "created_at": report.created_at.isoformat(),
        })

    return _append_seed_samples(samples, limit=limit) if include_seed else samples[:limit]


def _summarize_ops_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "sample_count": len(rows),
        "revenue_jpy": summarize_numeric([float(row["paid_price_jpy"]) for row in rows]),
        "actual_cost_jpy": summarize_numeric([float(row["total_cost_jpy"]) for row in rows]),
        "actual_margin_jpy": summarize_numeric([float(row["actual_margin_jpy"]) for row in rows]),
        "actual_margin_rate": summarize_numeric([float(row["actual_margin_rate"]) for row in rows]),
        "estimate_vs_actual_cost_delta_jpy": summarize_numeric(
            [
                float(row["estimate_vs_actual_cost_delta_jpy"])
                for row in rows
                if row.get("estimate_vs_actual_cost_delta_jpy") is not None
            ]
        ),
        "estimate_vs_actual_margin_delta_jpy": summarize_numeric(
            [
                float(row["estimate_vs_actual_margin_delta_jpy"])
                for row in rows
                if row.get("estimate_vs_actual_margin_delta_jpy") is not None
            ]
        ),
    }


def _price_band_label(price_jpy: float) -> str:
    band_size = 200
    lower = int(price_jpy // band_size) * band_size
    upper = lower + band_size - 1
    return f"{lower}-{upper}"


def _build_model_signature(model_plan: dict[str, Any]) -> str:
    if not model_plan:
        return ""
    ordered_keys = [
        "ocr_model",
        "parse_model",
        "analysis_model",
        "suggestion_model",
        "translation_model",
        "embedding_model",
    ]
    return "|".join(
        f"{key}:{model_plan.get(key, '')}"
        for key in ordered_keys
    )


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
