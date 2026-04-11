import secrets
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.models.order import Order
from backend.models.referral import Referral
from backend.routers._helpers import parse_order_id
from backend.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


class ReferralGenerateRequest(BaseModel):
    order_id: str


@router.post("/api/referral/generate")
async def generate_referral(
    request: ReferralGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate a referral code for a paid order."""
    settings = get_settings()
    order_uuid = parse_order_id(request.order_id)
    order_result = await db.execute(select(Order).where(Order.id == order_uuid))
    order = order_result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.payment_status != "paid":
        raise HTTPException(status_code=409, detail="Referral link is available after payment")

    existing_result = await db.execute(
        select(Referral).where(Referral.referrer_order_id == order_uuid)
    )
    existing_referral = existing_result.scalar_one_or_none()
    if existing_referral is not None:
        return {
            "referral_code": existing_referral.referral_code,
            "referral_url": f"{settings.FRONTEND_URL}/?ref={existing_referral.referral_code}",
            "discount_jpy": existing_referral.discount_jpy,
        }

    code = secrets.token_urlsafe(6).upper()[:8]

    referral = Referral(
        referrer_order_id=order_uuid,
        referral_code=code,
    )
    db.add(referral)
    await db.commit()

    return {
        "referral_code": code,
        "referral_url": f"{settings.FRONTEND_URL}/?ref={code}",
        "discount_jpy": referral.discount_jpy,
    }


@router.get("/api/referral/{code}")
async def check_referral(
    code: str,
    db: AsyncSession = Depends(get_db),
):
    """Check if a referral code is valid."""
    result = await db.execute(
        select(Referral).where(Referral.referral_code == code, Referral.is_active == True)
    )
    referral = result.scalar_one_or_none()

    if referral is None or referral.uses_count >= referral.max_uses:
        return {"valid": False}

    return {
        "valid": True,
        "discount_jpy": referral.discount_jpy,
    }
