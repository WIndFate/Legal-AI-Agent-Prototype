from pydantic import BaseModel


class ClauseAnalysis(BaseModel):
    clause_number: str
    risk_level: str
    risk_reason: str
    suggestion: str
    referenced_law: str
    original_text: str = ""


class ReportResponse(BaseModel):
    order_id: str
    report: dict
    language: str
    created_at: str
    expires_at: str
