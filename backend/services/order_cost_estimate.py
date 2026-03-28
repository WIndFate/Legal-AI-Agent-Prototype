from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.order import Order
from backend.models.order_cost_estimate import OrderCostEstimate
from backend.services.costing import estimate_cost_jpy, estimate_cost_usd
from backend.services.token_estimator import get_pricing_policy_metadata


TOKENS_PER_CLAUSE = 470


def get_model_plan() -> dict[str, str]:
    settings = get_settings()
    return {
        "ocr_model": settings.OCR_MODEL,
        "parse_model": settings.PARSE_MODEL,
        "analysis_model": settings.ANALYSIS_MODEL,
        "suggestion_model": settings.SUGGESTION_MODEL,
        "translation_model": settings.TRANSLATION_MODEL,
        "embedding_model": settings.EMBEDDING_MODEL,
    }


def build_order_cost_estimate_snapshot(order: Order) -> dict[str, Any]:
    model_plan = get_model_plan()
    pricing_policy = get_pricing_policy_metadata()
    predicted_clause_count = max(1, round(order.estimated_tokens / TOKENS_PER_CLAUSE))
    risk_rates = _risk_rates_for_order(order)

    predicted_high = min(predicted_clause_count, round(predicted_clause_count * risk_rates["high"]))
    predicted_medium = min(
        predicted_clause_count - predicted_high,
        round(predicted_clause_count * risk_rates["medium"]),
    )
    predicted_low = max(0, predicted_clause_count - predicted_high - predicted_medium)
    predicted_suggestion_calls = predicted_high + predicted_medium

    step_usage = _build_predicted_step_usage(order, predicted_clause_count, predicted_suggestion_calls)
    predicted_cost_breakdown = {}
    total_cost_usd = 0.0
    total_cost_jpy = 0.0
    for step_name, usage in step_usage.items():
        cost_usd = estimate_cost_usd(
            usage["model"],
            input_tokens=usage["input_tokens"],
            output_tokens=usage["output_tokens"],
            cached_input_tokens=usage.get("cached_input_tokens", 0),
        )
        cost_jpy = estimate_cost_jpy(
            usage["model"],
            input_tokens=usage["input_tokens"],
            output_tokens=usage["output_tokens"],
            cached_input_tokens=usage.get("cached_input_tokens", 0),
        )
        total_cost_usd += cost_usd
        total_cost_jpy += cost_jpy
        predicted_cost_breakdown[step_name] = {
            **usage,
            "estimated_cost_usd": round(cost_usd, 6),
            "estimated_cost_jpy": round(cost_jpy, 3),
        }

    predicted_margin_jpy = round(order.price_jpy - total_cost_jpy, 3)
    predicted_margin_rate = round((predicted_margin_jpy / order.price_jpy), 4) if order.price_jpy else 0.0

    return {
        "estimate_version": get_settings().COST_ESTIMATE_VERSION,
        "pricing_policy_version": pricing_policy.get("version"),
        "input_type": order.input_type,
        "quote_mode": order.quote_mode,
        "estimate_source": order.estimate_source,
        "target_language": order.target_language,
        "pricing_model": pricing_policy.get("pricing_model"),
        "unit_price_jpy_per_1k_tokens": int(pricing_policy.get("unit_price_jpy_per_1k_tokens") or 0),
        "minimum_price_jpy": int(pricing_policy.get("minimum_price_jpy") or 0),
        "estimated_tokens": order.estimated_tokens,
        "page_estimate": order.page_estimate,
        "predicted_clause_count": predicted_clause_count,
        "predicted_high_risk_count": predicted_high,
        "predicted_medium_risk_count": predicted_medium,
        "predicted_low_risk_count": predicted_low,
        "predicted_suggestion_calls": predicted_suggestion_calls,
        "predicted_translation_input_tokens": step_usage["translate_report"]["input_tokens"],
        "predicted_total_cost_usd": round(total_cost_usd, 6),
        "predicted_total_cost_jpy": round(total_cost_jpy, 3),
        "predicted_cost_breakdown": predicted_cost_breakdown,
        "quoted_price_jpy": order.price_jpy,
        "quoted_pricing_model": pricing_policy.get("pricing_model") or order.price_tier,
        "predicted_gross_margin_jpy": predicted_margin_jpy,
        "predicted_gross_margin_rate": predicted_margin_rate,
        "model_plan": model_plan,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def build_order_cost_actual_snapshot(
    order: Order,
    cost_summary: dict | None,
    report_data: dict | None = None,
) -> dict[str, Any] | None:
    if not cost_summary:
        return None

    report_data = report_data or {}
    actual_total_cost_jpy = float(cost_summary.get("total_cost_jpy", 0.0) or 0.0)
    actual_total_cost_usd = float(cost_summary.get("total_cost_usd", 0.0) or 0.0)
    actual_margin_jpy = round(order.price_jpy - actual_total_cost_jpy, 3)
    actual_margin_rate = round((actual_margin_jpy / order.price_jpy), 4) if order.price_jpy else 0.0
    step_cost_breakdown = {}
    for step_name, step_data in (cost_summary.get("steps") or {}).items():
        step_cost_breakdown[step_name] = {
            "calls": int(step_data.get("calls", 0) or 0),
            "cost_usd": round(float(step_data.get("cost_usd", 0.0) or 0.0), 6),
            "cost_jpy": round(float(step_data.get("cost_jpy", 0.0) or 0.0), 3),
            "input_tokens": int(step_data.get("input_tokens", 0) or 0),
            "output_tokens": int(step_data.get("output_tokens", 0) or 0),
            "cached_input_tokens": int(step_data.get("cached_input_tokens", 0) or 0),
            "models": step_data.get("models", {}),
        }

    return {
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "input_type": order.input_type,
        "quote_mode": order.quote_mode,
        "estimate_source": order.estimate_source,
        "target_language": order.target_language,
        "pricing_model": "token_linear" if order.price_tier == "token_linear" else order.price_tier,
        "actual_total_cost_usd": round(actual_total_cost_usd, 6),
        "actual_total_cost_jpy": round(actual_total_cost_jpy, 3),
        "actual_total_input_tokens": int(cost_summary.get("total_input_tokens", 0) or 0),
        "actual_total_output_tokens": int(cost_summary.get("total_output_tokens", 0) or 0),
        "actual_clause_count": int(report_data.get("total_clauses", 0) or cost_summary.get("total_clauses", 0) or 0),
        "actual_high_risk_count": int(report_data.get("high_risk_count", 0) or cost_summary.get("high_risk_count", 0) or 0),
        "actual_medium_risk_count": int(report_data.get("medium_risk_count", 0) or cost_summary.get("medium_risk_count", 0) or 0),
        "actual_low_risk_count": int(report_data.get("low_risk_count", 0) or cost_summary.get("low_risk_count", 0) or 0),
        "actual_suggestion_calls": int((cost_summary.get("steps") or {}).get("generate_suggestion", {}).get("calls", 0) or 0),
        "actual_cost_breakdown": step_cost_breakdown,
        "actual_model_breakdown": cost_summary.get("models", {}),
        "model_plan": _derive_actual_model_plan(cost_summary),
        "actual_gross_margin_jpy": actual_margin_jpy,
        "actual_gross_margin_rate": actual_margin_rate,
    }


def build_order_cost_comparison_snapshot(
    estimate_snapshot: dict[str, Any] | None,
    actual_snapshot: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not estimate_snapshot or not actual_snapshot:
        return None

    predicted_cost_jpy = float(estimate_snapshot.get("predicted_total_cost_jpy", 0.0) or 0.0)
    actual_cost_jpy = float(actual_snapshot.get("actual_total_cost_jpy", 0.0) or 0.0)
    predicted_cost_usd = float(estimate_snapshot.get("predicted_total_cost_usd", 0.0) or 0.0)
    actual_cost_usd = float(actual_snapshot.get("actual_total_cost_usd", 0.0) or 0.0)
    predicted_margin_jpy = float(estimate_snapshot.get("predicted_gross_margin_jpy", 0.0) or 0.0)
    actual_margin_jpy = float(actual_snapshot.get("actual_gross_margin_jpy", 0.0) or 0.0)
    predicted_margin_rate = float(estimate_snapshot.get("predicted_gross_margin_rate", 0.0) or 0.0)
    actual_margin_rate = float(actual_snapshot.get("actual_gross_margin_rate", 0.0) or 0.0)
    cost_delta_jpy = round(actual_cost_jpy - predicted_cost_jpy, 3)
    cost_delta_usd = round(actual_cost_usd - predicted_cost_usd, 6)

    return {
        "cost_delta_jpy": cost_delta_jpy,
        "cost_delta_usd": cost_delta_usd,
        "cost_delta_rate": round((cost_delta_jpy / predicted_cost_jpy), 4) if predicted_cost_jpy else 0.0,
        "margin_delta_jpy": round(actual_margin_jpy - predicted_margin_jpy, 3),
        "margin_delta_rate": round(actual_margin_rate - predicted_margin_rate, 4),
        "clause_count_delta": int(actual_snapshot.get("actual_clause_count", 0) or 0)
        - int(estimate_snapshot.get("predicted_clause_count", 0) or 0),
        "suggestion_call_delta": int(actual_snapshot.get("actual_suggestion_calls", 0) or 0)
        - int(estimate_snapshot.get("predicted_suggestion_calls", 0) or 0),
        "high_risk_delta": int(actual_snapshot.get("actual_high_risk_count", 0) or 0)
        - int(estimate_snapshot.get("predicted_high_risk_count", 0) or 0),
        "medium_risk_delta": int(actual_snapshot.get("actual_medium_risk_count", 0) or 0)
        - int(estimate_snapshot.get("predicted_medium_risk_count", 0) or 0),
        "low_risk_delta": int(actual_snapshot.get("actual_low_risk_count", 0) or 0)
        - int(estimate_snapshot.get("predicted_low_risk_count", 0) or 0),
        "is_underestimated": actual_cost_jpy > predicted_cost_jpy,
        "is_overestimated": actual_cost_jpy < predicted_cost_jpy,
    }


async def upsert_order_cost_estimate(
    db: AsyncSession,
    *,
    order: Order,
    estimate_snapshot: dict[str, Any] | None = None,
    actual_snapshot: dict[str, Any] | None = None,
    comparison_snapshot: dict[str, Any] | None = None,
) -> OrderCostEstimate:
    result = await db.execute(select(OrderCostEstimate).where(OrderCostEstimate.order_id == order.id))
    record = result.scalar_one_or_none()
    if record is None:
        record = OrderCostEstimate(
            order_id=order.id,
            estimate_version=get_settings().COST_ESTIMATE_VERSION,
            pricing_policy_version=(estimate_snapshot or {}).get("pricing_policy_version"),
            estimate_snapshot=estimate_snapshot or {},
            actual_snapshot=actual_snapshot,
            comparison_snapshot=comparison_snapshot,
        )
        db.add(record)
    else:
        if estimate_snapshot is not None:
            record.estimate_version = str(estimate_snapshot.get("estimate_version") or record.estimate_version)
            record.pricing_policy_version = estimate_snapshot.get("pricing_policy_version")
            record.estimate_snapshot = estimate_snapshot
        if actual_snapshot is not None:
            record.actual_snapshot = actual_snapshot
        if comparison_snapshot is not None:
            record.comparison_snapshot = comparison_snapshot
    flush = getattr(db, "flush", None)
    if flush is not None:
        await flush()
    return record


async def clear_order_cost_actuals(db: AsyncSession, order_id: str) -> None:
    result = await db.execute(select(OrderCostEstimate).where(OrderCostEstimate.order_id == order_id))
    record = result.scalar_one_or_none()
    if record is None:
        return
    record.actual_snapshot = None
    record.comparison_snapshot = None
    flush = getattr(db, "flush", None)
    if flush is not None:
        await flush()


def _build_predicted_step_usage(order: Order, clause_count: int, suggestion_calls: int) -> dict[str, dict[str, Any]]:
    model_plan = get_model_plan()
    parse_input_tokens = max(600, int(order.estimated_tokens * 0.82))
    parse_output_tokens = max(300, min(int(order.estimated_tokens * 0.48), clause_count * 220))
    analyze_input_tokens = clause_count * (860 + order.page_estimate * 12)
    analyze_output_tokens = clause_count * 125
    suggestion_input_tokens = suggestion_calls * 340
    suggestion_output_tokens = suggestion_calls * 95
    translation_input_tokens = max(700, int(clause_count * 175 + suggestion_calls * 70 + 900))
    translation_output_tokens = max(500, int(translation_input_tokens * 0.72))
    embedding_input_tokens = max(200, clause_count * 175)

    usage: dict[str, dict[str, Any]] = {
        "parse_contract": {
            "model": model_plan["parse_model"],
            "input_tokens": parse_input_tokens,
            "output_tokens": parse_output_tokens,
            "cached_input_tokens": 0,
            "calls": 1,
        },
        "embedding_batch": {
            "model": model_plan["embedding_model"],
            "input_tokens": embedding_input_tokens,
            "output_tokens": 0,
            "cached_input_tokens": 0,
            "calls": 1,
        },
        "analyze_clause": {
            "model": model_plan["analysis_model"],
            "input_tokens": analyze_input_tokens,
            "output_tokens": analyze_output_tokens,
            "cached_input_tokens": 0,
            "calls": clause_count,
        },
        "generate_suggestion": {
            "model": model_plan["suggestion_model"],
            "input_tokens": suggestion_input_tokens,
            "output_tokens": suggestion_output_tokens,
            "cached_input_tokens": 0,
            "calls": suggestion_calls,
        },
        "translate_report": {
            "model": model_plan["translation_model"],
            "input_tokens": translation_input_tokens,
            "output_tokens": translation_output_tokens,
            "cached_input_tokens": 0,
            "calls": 1,
        },
    }

    if order.input_type in {"image", "pdf"} and order.quote_mode == "estimated_pre_ocr":
        usage["ocr_formal"] = {
            "model": model_plan["ocr_model"],
            "input_tokens": max(1200, order.page_estimate * 1200),
            "output_tokens": max(500, int(order.estimated_tokens * 0.85)),
            "cached_input_tokens": 0,
            "calls": max(1, order.page_estimate),
        }

    return usage


def _risk_rates_for_order(order: Order) -> dict[str, float]:
    high_rate = 0.06
    medium_rate = 0.27

    if order.page_estimate >= 3:
        high_rate += 0.01
        medium_rate += 0.02
    if order.page_estimate >= 6:
        high_rate += 0.02
        medium_rate += 0.03
    if order.page_estimate >= 10:
        high_rate += 0.02
        medium_rate += 0.03

    if order.input_type in {"image", "pdf"} and order.quote_mode == "estimated_pre_ocr":
        high_rate += 0.01
        medium_rate += 0.03

    return {
        "high": min(high_rate, 0.18),
        "medium": min(medium_rate, 0.45),
    }


def _derive_actual_model_plan(cost_summary: dict[str, Any]) -> dict[str, str]:
    steps = cost_summary.get("steps") or {}
    return {
        "ocr_model": _pick_primary_model((steps.get("ocr_formal") or {}).get("models")),
        "parse_model": _pick_primary_model((steps.get("parse_contract") or {}).get("models")),
        "analysis_model": _pick_primary_model((steps.get("analyze_clause") or {}).get("models")),
        "suggestion_model": _pick_primary_model((steps.get("generate_suggestion") or {}).get("models")),
        "translation_model": _pick_primary_model((steps.get("translate_report") or {}).get("models")),
        "embedding_model": _pick_primary_model((steps.get("embedding_batch") or {}).get("models")),
    }


def _pick_primary_model(models: dict[str, Any] | None) -> str:
    if not models:
        return ""
    return max(
        models.items(),
        key=lambda item: (
            float(item[1].get("cost_jpy", 0.0) or 0.0),
            int(item[1].get("calls", 0) or 0),
        ),
    )[0]
