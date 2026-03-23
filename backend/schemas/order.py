from pydantic import BaseModel


class ReviewStreamRequest(BaseModel):
    order_id: str
