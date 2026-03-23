from pydantic import BaseModel


class PiiWarning(BaseModel):
    type: str
    start: int
    end: int
    text: str


class UploadResponse(BaseModel):
    contract_text: str
    estimated_tokens: int
    page_estimate: int
    price_tier: str
    price_jpy: int
    pii_warnings: list[PiiWarning]
