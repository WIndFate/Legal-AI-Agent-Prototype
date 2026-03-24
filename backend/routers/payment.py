import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.models.order import Order
from backend.models.referral import Referral
from backend.schemas.payment import PaymentCreateRequest, PaymentCreateResponse
from backend.services.payment import create_payment_session, verify_webhook
from backend.services.analytics import capture as posthog_capture

try:
    import sentry_sdk
except ImportError:
    sentry_sdk = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/payment/create", response_model=PaymentCreateResponse)
async def create_payment(
    request: PaymentCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create an order and KOMOJU payment session. Apply referral discount if valid."""
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
            referral.uses_count += 1
        else:
            logger.info("Invalid or exhausted referral code: %s", request.referral_code)

    final_price = max(0, request.price_jpy - discount_jpy)

    # Create order in database
    order = Order(
        email=request.email,
        contract_text=request.contract_text,
        input_type=request.input_type,
        estimated_tokens=request.estimated_tokens,
        page_estimate=request.estimated_tokens // 1500 or 1,
        price_tier=request.price_tier,
        price_jpy=final_price,
        target_language=request.target_language,
        referral_code_used=request.referral_code,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    # Create KOMOJU payment session
    session_url = await create_payment_session(
        order_id=str(order.id),
        amount_jpy=final_price,
        email=request.email,
    )

    posthog_capture(
        request.email,
        "payment_created",
        {
            "order_id": str(order.id),
            "price_jpy": final_price,
            "price_tier": request.price_tier,
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
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event_type = event.get("type", "")
    logger.info("Payment webhook received: %s", event_type)

    if event_type == "payment.captured":
        payment_data = event.get("data", {})
        order_id = payment_data.get("metadata", {}).get("order_id")
        if order_id:
            from datetime import datetime, timezone
            result = await db.execute(
                select(Order).where(Order.id == order_id)
            )
            order = result.scalar_one_or_none()
            if order and order.payment_status != "paid":
                order.payment_status = "paid"
                order.paid_at = datetime.now(timezone.utc)
                order.komoju_session_id = payment_data.get("id", "")
                await db.commit()
                logger.info("Order %s marked as paid", order_id)
                posthog_capture(
                    order.email or order_id,
                    "payment_captured",
                    {"order_id": order_id, "price_jpy": order.price_jpy},
                )

    return {"ok": True}


@router.get("/api/payment/status/{order_id}")
async def payment_status(
    order_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Check payment status for an order."""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"order_id": str(order.id), "status": order.payment_status}
