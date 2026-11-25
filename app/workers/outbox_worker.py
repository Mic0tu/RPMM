"""Continuously publishes committed outbox rows to RabbitMQ."""
import asyncio
import json

import structlog

from app.core.rabbitmq import publish_event
from app.core.logging import setup_logging
from app.core.observability import configure_telemetry
from app.database import SessionLocal
from app.models import OutboxEvent
from app.modules.orders.repository import OrderRepository

logger = structlog.get_logger()


async def publish_pending_once() -> int:
    db = SessionLocal()
    try:
        repo = OrderRepository(db)
        events = repo.pending_outbox(limit=1)
        published = 0
        for event in events:
            try:
                await publish_event(
                    event.routing_key,
                    json.loads(event.payload),
                    event.correlation_id,
                    json.loads(event.trace_context or "{}"),
                )
                repo.mark_outbox_published(event)
                logger.info(
                    "outbox_event_published",
                    event_id=event.id,
                    routing_key=event.routing_key,
                    correlation_id=event.correlation_id,
                )
                published += 1
            except Exception as exc:
                repo.mark_outbox_failed(event, repr(exc))
                logger.exception(
                    "outbox_publish_failed",
                    event_id=event.id,
                    correlation_id=event.correlation_id,
                )
        return published
    finally:
        db.close()


async def main() -> None:
    setup_logging()
    configure_telemetry("sirius-outbox-publisher")
    while True:
        await publish_pending_once()
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
