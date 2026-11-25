"""Independent event consumer representing the delivery service."""
import asyncio
import json

import structlog
from opentelemetry import propagate, trace

from app.core.events import connect_consumer, declare_consumer_topology, retry_or_dead_letter
from app.core.logging import setup_logging
from app.core.observability import configure_telemetry
from app.database import SessionLocal
from app.models import ProcessedEvent

logger = structlog.get_logger()


async def process_message(message, exchange, dead_exchange) -> None:
    headers = dict(message.headers or {})
    correlation_id = str(headers.get("X-Correlation-ID", "unknown"))
    context = propagate.extract(headers)
    try:
        with trace.get_tracer(__name__).start_as_current_span("delivery.consume", context=context) as span:
            payload = json.loads(message.body)
            event_id = str(payload["event_id"])
            order_id = int(payload["order_id"])
            span.set_attribute("messaging.message.id", event_id)
            span.set_attribute("order.id", order_id)
            db = SessionLocal()
            try:
                existing = db.query(ProcessedEvent).filter_by(
                    id=event_id, consumer="delivery"
                ).first()
                if not existing:
                    db.add(ProcessedEvent(id=event_id, consumer="delivery"))
                    db.commit()

                    from app.models import User, Role
                    courier = db.query(User).join(Role).filter(
                        Role.name == "courier", 
                        User.is_blocked == False
                    ).first()

                    if not courier:
                        logger.warning("no_courier_available", order_id=order_id)
                        from app.core.rabbitmq import publish_event
                        import uuid
                        await publish_event(
                            "delivery.failed", 
                            {
                                "event_id": str(uuid.uuid4()),
                                "order_id": order_id, 
                                "reason": "No courier available"
                            }
                        )
                    else:
                        logger.info("delivery_assigned", order_id=order_id, courier_id=courier.id)
                else:
                    logger.info("delivery_duplicate_ignored", order_id=order_id)
            finally:
                db.close()
        await message.ack()
    except Exception:
        logger.exception(
            "delivery_message_failed",
            correlation_id=correlation_id,
            retry_count=headers.get("x-retry-count", 0),
        )
        try:
            result = await retry_or_dead_letter(message, "delivery", exchange, dead_exchange)
            logger.warning("delivery_message_" + result, correlation_id=correlation_id)
        except Exception:
            logger.exception("delivery_retry_publish_failed", correlation_id=correlation_id)
            await message.nack(requeue=True)


async def main() -> None:
    setup_logging()
    configure_telemetry("sirius-delivery")
    connection, channel = await connect_consumer()
    queue, exchange, dead_exchange = await declare_consumer_topology(
        channel, "delivery", "order.paid"
    )
    await queue.consume(lambda message: process_message(message, exchange, dead_exchange))
    logger.info("delivery_consumer_started", queue="delivery_queue")
    try:
        await asyncio.Future()
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
 