from pydantic import BaseModel, EmailStr


class PaymentCreateRequest(BaseModel):
    email: EmailStr
    contract_text: str
    input_type: str
    estimated_tokens: int
    price_jpy: int
    quote_mode: str = "exact"
    estimate_source: str = "raw_text"
    upload_token: str | None = None
    upload_name: str | None = None
    upload_mime_type: str | None = None
    target_language: str = "ja"
    referral_code: str | None = None


class PaymentCreateResponse(BaseModel):
    order_id: str
    komoju_session_url: str
    price_jpy: int
    discount_applied: int = 0
