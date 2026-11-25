"""Durable RabbitMQ topology and bounded retry/DLQ helpers."""
import aio_pika
from aio_pika import ExchangeType

from app.core.config import settings
from app.core.rabbitmq import EXCHANGE_NAME

DEAD_EXCHANGE = "dlx_exchange"
MAX_DELIVERY_ATTEMPTS = 3


async def declare_consumer_topology(channel: aio_pika.abc.AbstractChannel, name: str, routing_key: str):
    """Create a main queue, TTL retry queue, and dead-letter queue for a consumer."""
    exchange = await channel.declare_exchange(EXCHANGE_NAME, ExchangeType.TOPIC, durable=True)
    dead_exchange = await channel.declare_exchange(DEAD_EXCHANGE, ExchangeType.DIRECT, durable=True)

    queue = await channel.declare_queue(
        f"{name}_queue",
        durable=True,
        arguments={
            "x-dead-letter-exchange": DEAD_EXCHANGE,
            "x-dead-letter-routing-key": f"{name}.dlq",
        },
    )
    await queue.bind(exchange, routing_key=routing_key)
    await queue.bind(exchange, routing_key=f"retry.{name}")

    retry_queue = await channel.declare_queue(
        f"{name}_retry",
        durable=True,
        arguments={
            "x-message-ttl": 3000,
            "x-dead-letter-exchange": EXCHANGE_NAME,
            "x-dead-letter-routing-key": f"retry.{name}",
        },
    )
    await retry_queue.bind(exchange, routing_key=f"retry.{name}.delay")

    dead_queue = await channel.declare_queue(f"{name}_dlq", durable=True)
    await dead_queue.bind(dead_exchange, routing_key=f"{name}.dlq")
    return queue, exchange, dead_exchange


async def retry_or_dead_letter(
    message: aio_pika.IncomingMessage,
    name: str,
    exchange: aio_pika.abc.AbstractExchange,
    dead_exchange: aio_pika.abc.AbstractExchange,
) -> str:
    """Republish a failed message with an incremented attempt counter."""
    headers = dict(message.headers or {})
    attempts = int(headers.get("x-retry-count", 0))
    headers["x-retry-count"] = attempts + 1
    if attempts + 1 >= MAX_DELIVERY_ATTEMPTS:
        await dead_exchange.publish(
            aio_pika.Message(
                body=message.body,
                headers=headers,
                content_type=message.content_type,
                message_id=message.message_id,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=f"{name}.dlq",
            mandatory=True,
        )
        await message.ack()
        return "dead_letter"

    await exchange.publish(
        aio_pika.Message(
            body=message.body,
            headers=headers,
            content_type=message.content_type,
            message_id=message.message_id,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            expiration=3000,
        ),
        routing_key=f"retry.{name}.delay",
        mandatory=True,
    )
    await message.ack()
    return "retry"


async def connect_consumer():
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)
    return connection, channel
