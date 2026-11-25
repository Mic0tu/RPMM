"""Create event queues and capped retry/dead-letter topology."""
import asyncio

from aio_pika import ExchangeType

from app.core.config import settings
from app.core.events import DEAD_EXCHANGE, declare_consumer_topology
from app.core.logging import setup_logging
import aio_pika
import structlog

logger = structlog.get_logger()


async def setup() -> None:
    setup_logging()
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    try:
        channel = await connection.channel()
        await channel.declare_exchange(DEAD_EXCHANGE, ExchangeType.DIRECT, durable=True)
        for name, route in (
            ("kitchen", "order.paid"),
            ("delivery", "order.paid"),
            ("saga", "delivery.failed"),
        ):
            await declare_consumer_topology(channel, name, route)
        logger.info("rabbitmq_event_topology_ready")
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(setup())
