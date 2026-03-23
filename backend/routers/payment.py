import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.models.order import Order
from backend.schemas.payment import PaymentCreateRequest, PaymentCreateResponse
from backend.services.payment import create_payment_session, verify_webhook

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/payment/create", response_model=PaymentCreateResponse)
async def create_payment(
    request: PaymentCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create an order and KOMOJU payment session."""
    # Create order in database
    order = Order(
        email=request.email,
        contract_text=request.contract_text,
        input_type=request.input_type,
        estimated_tokens=request.estimated_tokens,
        page_estimate=request.estimated_tokens // 1500 or 1,
        price_tier=request.price_tier,
        price_jpy=request.price_jpy,
        target_language=request.target_language,
        referral_code_used=request.referral_code,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    # Create KOMOJU payment session
    session_url = await create_payment_session(
        order_id=str(order.id),
        amount_jpy=request.price_jpy,
        email=request.email,
    )

    return PaymentCreateResponse(
        order_id=str(order.id),
        komoju_session_url=session_url,
        price_jpy=request.price_jpy,
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

    # TODO: Update order payment_status based on event type
    logger.info(f"Payment webhook received: {event.get('type')}")
    return {"ok": True}
