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
    detected_input_type: str
    estimated_tokens: int
    price_jpy: int
    quote_mode: str = "exact"
    estimate_source: str = "raw_text"
    quote_token: str | None = None
    clause_preview: list[ClausePreviewItem] | None = None
    clause_count: int | None = None
    is_contract: bool | None = None
    pii_warnings: list[PiiWarning]
