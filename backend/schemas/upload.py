from pydantic import BaseModel


class PiiWarning(BaseModel):
    type: str
    start: int
    end: int
    text: str


class ClausePreviewItem(BaseModel):
    number: str
    title: str


class UploadResponse(BaseModel):
    contract_text: str
    estimated_tokens: int
    price_jpy: int
    quote_mode: str = "exact"
    estimate_source: str = "raw_text"
    quote_token: str | None = None
    ocr_required: bool = False
    ocr_confidence: str | None = None
    ocr_warnings: list[str] = []
    clause_preview: list[ClausePreviewItem] | None = None
    clause_count: int | None = None
    is_contract: bool | None = None
    upload_token: str | None = None
    upload_name: str | None = None
    upload_mime_type: str | None = None
    pii_warnings: list[PiiWarning]
