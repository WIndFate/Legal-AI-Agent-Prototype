from uuid import UUID

from fastapi import HTTPException


def parse_order_id(order_id: str) -> UUID:
    # Invalid UUID strings map to 404 so mistyped order IDs behave like
    # "order does not exist" instead of surfacing an asyncpg DataError as 500.
    try:
        return UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Order not found")
