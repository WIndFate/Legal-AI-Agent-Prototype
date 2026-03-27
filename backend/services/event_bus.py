import asyncio
from collections import defaultdict


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, order_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._subscribers[order_id].add(queue)
        return queue

    async def unsubscribe(self, order_id: str, queue: asyncio.Queue) -> None:
        async with self._lock:
            subscribers = self._subscribers.get(order_id)
            if not subscribers:
                return
            subscribers.discard(queue)
            if not subscribers:
                self._subscribers.pop(order_id, None)

    async def publish(self, order_id: str, event: dict) -> None:
        async with self._lock:
            subscribers = list(self._subscribers.get(order_id, set()))
        for queue in subscribers:
            await queue.put(event)


event_bus = EventBus()
