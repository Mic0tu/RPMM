"""Idempotent kitchen consumer for OrderPaid events."""
import asyncio
import json

import structlog
from opentelemetry import propagate, trace

from app.core.events import connect_consumer, declare_consumer_topology, retry_or_dead_letter
from app.core.logging import setup_logging
from app.core.observability import configure_telemetry
from app.database import SessionLocal
from app.models import KitchenOrder, ProcessedEvent

logger = structlog.get_logger()


async def process_message(message, exchange, dead_exchange) -> None:
    headers = dict(message.headers or {})
    correlation_id = str(headers.get("X-Correlation-ID", "unknown"))
    context = propagate.extract(headers)
    tracer = trace.get_tracer(__name__)
    try:
        with tracer.start_as_current_span("kitchen.consume", context=context) as span:
            payload = json.loads(message.body)
            event_id = str(payload["event_id"])
            order_id = int(payload["order_id"])
            span.set_attribute("messaging.message.id", event_id)
            span.set_attribute("order.id", order_id)
            db = SessionLocal()
            try:
                existing = db.query(ProcessedEvent).filter_by(
                    id=event_id, consumer="kitchen"
                ).first()
                if not existing:
                    db.add(KitchenOrder(order_id=order_id, status="pending"))
                    db.add(ProcessedEvent(id=event_id, consumer="kitchen"))
                    db.commit()
                    logger.info(
                        "kitchen_order_received",
                        order_id=order_id,
                        event_id=event_id,
                        correlation_id=correlation_id,
                    )
                else:
                    logger.info(
                        "kitchen_duplicate_ignored",
                        order_id=order_id,
                        event_id=event_id,
                        correlation_id=correlation_id,
                    )
            finally:
                db.close()
        await message.ack()
    except Exception:
        logger.exception(
            "kitchen_message_failed",
            correlation_id=correlation_id,
            retry_count=headers.get("x-retry-count", 0),
        )
        try:
            result = await retry_or_dead_letter(message, "kitchen", exchange, dead_exchange)
            logger.warning("kitchen_message_" + result, correlation_id=correlation_id)
        except Exception:
            logger.exception("kitchen_retry_publish_failed", correlation_id=correlation_id)
            await message.nack(requeue=True)


async def main() -> None:
    setup_logging()
    configure_telemetry("sirius-kitchen")
    connection, channel = await connect_consumer()
    queue, exchange, dead_exchange = await declare_consumer_topology(
        channel, "kitchen", "order.paid"
    )
    await queue.consume(lambda message: process_message(message, exchange, dead_exchange))
    logger.info("kitchen_consumer_started", queue="kitchen_queue")
    try:
        await asyncio.Future()
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
 