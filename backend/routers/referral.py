import secrets
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.models.referral import Referral
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
    code = secrets.token_urlsafe(6).upper()[:8]
    settings = get_settings()

    referral = Referral(
        referrer_order_id=request.order_id,
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
