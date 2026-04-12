import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.models.order import Order
from backend.models.referral import Referral
from backend.dependencies import get_redis
from backend.routers._helpers import parse_order_id
from backend.schemas.payment import PaymentCreateRequest, PaymentCreateResponse
from backend.services.order_cost_estimate import build_order_cost_estimate_snapshot, upsert_order_cost_estimate
from backend.services.payment import (
    create_payment_session,
    verify_webhook,
    is_dev_payment_mode,
    resolve_frontend_base_url,
)
from backend.services.analytics import capture as posthog_capture
from backend.services.analytics import capture_message as sentry_capture_message
from backend.services.quote_guard import build_contract_content_hash, load_quote_context
from backend.services.token_estimator import estimate_page_count_from_tokens

logger = logging.getLogger(__name__)

router = APIRouter()


def _validate_exact_quote_context(request: PaymentCreateRequest, quote_context: dict | None) -> None:
    if request.quote_mode != "exact":
        return
    if not request.quote_token or quote_context is None:
        raise HTTPException(
            status_code=409,
            detail="Exact quote expired or missing. Please upload the contract again before payment.",
        )

    expected_hash = quote_context.get("content_hash")
    actual_hash = build_contract_content_hash(request.contract_text)
    if isinstance(expected_hash, str) and expected_hash != actual_hash:
        raise HTTPException(
            status_code=409,
            detail="Exact quote no longer matches the uploaded contract. Please upload again.",
        )

    if quote_context.get("is_contract") is False:
        raise HTTPException(
            status_code=409,
            detail="The uploaded content was identified as non-contract material. Please upload a contract before payment.",
        )


@router.post("/api/payment/create", response_model=PaymentCreateResponse)
async def create_payment(
    raw_request: Request,
    request: PaymentCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create an order and KOMOJU payment session. Apply referral discount if valid."""
    logger.info(
        "Creating payment order: email=%s input_type=%s pricing_model=%s target_language=%s has_referral=%s",
        request.email,
        request.input_type,
        "token_linear",
        request.target_language,
        request.referral_code is not None,
    )
    redis = await get_redis()
    quote_context = await load_quote_context(redis, request.quote_token)
    _validate_exact_quote_context(request, quote_context)

    # Validate and apply referral discount
    discount_jpy = 0
    if request.referral_code:
        ref_result = await db.execute(
            select(Referral).where(
                Referral.referral_code == request.referral_code,
                Referral.is_active == True,
            )
        )
        referral = ref_result.scalar_one_or_none()
        if referral and referral.uses_count < referral.max_uses:
            discount_jpy = referral.discount_jpy
        else:
            logger.info("Invalid or exhausted referral code: %s", request.referral_code)
            posthog_capture(
                request.email,
                "referral_rejected",
                {"referral_code": request.referral_code, "reason": "invalid_or_exhausted"},
            )

    final_price = max(0, request.price_jpy - discount_jpy)

    # Create order in database
    order = Order(
        email=request.email,
        contract_text=request.contract_text,
        input_type=request.input_type,
        estimated_tokens=request.estimated_tokens,
        page_estimate=estimate_page_count_from_tokens(request.estimated_tokens),
        pricing_model="token_linear",
        price_jpy=final_price,
        quote_mode=request.quote_mode,
        estimate_source=request.estimate_source,
        temp_upload_token=request.upload_token,
        temp_upload_name=request.upload_name,
        temp_upload_mime_type=request.upload_mime_type,
        target_language=request.target_language,
        referral_code_used=request.referral_code,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    estimate_snapshot = build_order_cost_estimate_snapshot(order, prepayment_quote=quote_context)
    await upsert_order_cost_estimate(db, order=order, estimate_snapshot=estimate_snapshot)
    await db.commit()
    logger.info(
        "Payment order created: order_id=%s final_price=%s discount_jpy=%s",
        order.id,
        final_price,
        discount_jpy,
    )

    if is_dev_payment_mode():
        order.payment_status = "paid"
        order.paid_at = datetime.now(timezone.utc)
        order.komoju_session_id = "dev-payment"
        await db.commit()
        logger.info("Dev payment bypass applied: order_id=%s", order.id)
        posthog_capture(
            request.email,
            "payment_marked_paid_in_dev",
            {"order_id": str(order.id), "price_jpy": final_price},
        )

    frontend_base_url = resolve_frontend_base_url(
        origin_header=raw_request.headers.get("origin"),
        referer_header=raw_request.headers.get("referer"),
        forwarded_proto=raw_request.headers.get("x-forwarded-proto"),
        forwarded_host=raw_request.headers.get("x-forwarded-host"),
        host_header=raw_request.headers.get("host"),
    )

    # Create KOMOJU payment session
    session_url = await create_payment_session(
        order_id=str(order.id),
        amount_jpy=final_price,
        email=request.email,
        frontend_base_url=frontend_base_url,
    )
    logger.info("Payment session prepared: order_id=%s session_url=%s", order.id, session_url)

    posthog_capture(
        request.email,
        "payment_created",
        {
            "order_id": str(order.id),
            "price_jpy": final_price,
            "pricing_model": "token_linear",
            "discount_jpy": discount_jpy,
            "has_referral": request.referral_code is not None,
        },
    )

    return PaymentCreateResponse(
        order_id=str(order.id),
        komoju_session_url=session_url,
        price_jpy=final_price,
        discount_applied=discount_jpy,
    )


@router.post("/api/payment/webhook")
async def payment_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle KOMOJU payment webhook."""
    body = await request.body()
    signature = request.headers.get("x-komoju-signature", "")

    event = await verify_webhook(body, signature)
    if event is None:
        logger.warning("Payment webhook rejected: reason=invalid_signature")
        posthog_capture("anonymous", "payment_webhook_rejected", {"reason": "invalid_signature"})
        sentry_capture_message(
            "KOMOJU webhook signature rejected",
            level="error",
            tags={"component": "payment_webhook", "reason": "invalid_signature"},
        )
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event_type = event.get("type", "")
    logger.info("Payment webhook received: %s", event_type)

    if event_type == "payment.captured":
        payment_data = event.get("data", {})
        order_id = payment_data.get("metadata", {}).get("order_id")
        if order_id:
            try:
                order_uuid = UUID(order_id)
            except ValueError:
                logger.warning("Payment webhook malformed order_id: order_id=%s", order_id)
                posthog_capture("anonymous", "payment_webhook_malformed_order_id", {"order_id": order_id})
                return {"ok": True}
            result = await db.execute(
                select(Order).where(Order.id == order_uuid)
            )
            order = result.scalar_one_or_none()
            if order is None:
                logger.warning("Payment webhook order missing: order_id=%s", order_id)
                posthog_capture("anonymous", "payment_webhook_order_missing", {"order_id": order_id})
            if order and order.payment_status != "paid":
                order.payment_status = "paid"
                order.paid_at = datetime.now(timezone.utc)
                order.komoju_session_id = payment_data.get("id", "")

                if order.referral_code_used:
                    referral_result = await db.execute(
                        select(Referral).where(Referral.referral_code == order.referral_code_used)
                    )
                    referral = referral_result.scalar_one_or_none()
                    if referral and referral.uses_count < referral.max_uses:
                        referral.uses_count += 1

                await db.commit()
                logger.info("Order %s marked as paid", order_id)
                posthog_capture(
                    order.email or order_id,
                    "payment_captured",
                    {"order_id": order_id, "price_jpy": order.price_jpy},
                )
            elif order and order.payment_status == "paid":
                logger.info("Payment webhook ignored: order_id=%s reason=already_paid", order_id)
                posthog_capture(
                    order.email or order_id,
                    "payment_webhook_ignored",
                    {"order_id": order_id, "reason": "already_paid"},
                )
        else:
            logger.warning("Payment webhook missing order_id in metadata")
            posthog_capture("anonymous", "payment_webhook_missing_order_id", {"event_type": event_type})

    return {"ok": True}


@router.get("/api/payment/status/{order_id}")
async def payment_status(
    order_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Check payment status for an order."""
    order_uuid = parse_order_id(order_id)
    result = await db.execute(select(Order).where(Order.id == order_uuid))
    order = result.scalar_one_or_none()
    if order is None:
        logger.warning("Payment status lookup failed: order_id=%s", order_id)
        raise HTTPException(status_code=404, detail="Order not found")
    logger.info("Payment status lookup: order_id=%s status=%s", order_id, order.payment_status)
    posthog_capture(
        order.email or order_id,
        "payment_status_checked",
        {"order_id": order_id, "status": order.payment_status},
    )
    return {"order_id": str(order.id), "status": order.payment_status}
