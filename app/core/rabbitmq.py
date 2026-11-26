"""RabbitMQ publisher shared by the API and background workers."""
import json

import aio_pika
from aio_pika import ExchangeType
from opentelemetry import propagate, trace

from app.core.config import settings

EXCHANGE_NAME = "sirius_events"


async def get_connection() -> aio_pika.RobustConnection:
    return await aio_pika.connect_robust(settings.RABBITMQ_URL)


async def publish_event(
    routing_key: str,
    payload: dict,
    correlation_id: str = "unknown",
    trace_context: dict[str, str] | None = None,
) -> None:
    """Publish a persistent event and propagate correlation/trace context."""
    connection = await get_connection()
    async with connection:
        channel = await connection.channel(
            publisher_confirms=True, on_return_raises=True
        )
        exchange = await channel.declare_exchange(
            EXCHANGE_NAME, ExchangeType.TOPIC, durable=True
        )
        
        parent = propagate.extract(trace_context or {})
        
        with trace.get_tracer(__name__).start_as_current_span(
            "rabbitmq.publish", context=parent
        ) as span:
            span.set_attribute("messaging.destination.name", routing_key)
            
            headers: dict[str, str] = {"X-Correlation-ID": str(correlation_id)}
            propagate.inject(headers)
            
            await exchange.publish(
                aio_pika.Message(
                    body=json.dumps(payload).encode(),
                    content_type="application/json",
                    headers=headers,
                    message_id=str(payload.get("event_id", "")),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key=routing_key,
                mandatory=True,
            )