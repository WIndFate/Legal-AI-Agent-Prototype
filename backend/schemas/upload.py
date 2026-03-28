from pydantic import BaseModel


class PiiWarning(BaseModel):
    type: str
    start: int
    end: int
    text: str


class UploadResponse(BaseModel):
    contract_text: str
    estimated_tokens: int
    price_jpy: int
    quote_mode: str = "exact"
    estimate_source: str = "raw_text"
    ocr_required: bool = False
    upload_token: str | None = None
    upload_name: str | None = None
    upload_mime_type: str | None = None
    pii_warnings: list[PiiWarning]
