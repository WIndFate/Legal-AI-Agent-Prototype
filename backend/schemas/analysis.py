from datetime import datetime

from pydantic import BaseModel


class AnalysisStartRequest(BaseModel):
    order_id: str


class AnalysisStartResponse(BaseModel):
    job_id: str
    order_id: str
    status: str


class OrderStatusResponse(BaseModel):
    order_id: str
    payment_status: str
    analysis_status: str
    current_step: str | None = None
    progress_message: str | None = None
    progress_seq: int = 0
    report_ready: bool = False
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AnalysisEventItem(BaseModel):
    seq: int
    event_type: str
    step: str | None = None
    message: str | None = None
    payload_json: dict | None = None
    created_at: datetime


class AnalysisEventsResponse(BaseModel):
    order_id: str
    events: list[AnalysisEventItem]
