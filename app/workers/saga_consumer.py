"""Saga-воркер: слушает delivery.failed и возвращает деньги."""
import asyncio
import json

import structlog
from opentelemetry import propagate, trace

from app.core.events import connect_consumer, declare_consumer_topology
from app.core.logging import setup_logging
from app.core.observability import configure_telemetry
from app.database import SessionLocal
from app.models import ProcessedEvent, Order, User

logger = structlog.get_logger()

async def process_message(message, exchange, dead_exchange) -> None:
    try:
        payload = json.loads(message.body)
        event_id = str(payload["event_id"])
        order_id = int(payload["order_id"])

        db = SessionLocal()
        try:
            # Проверка идемпотентности Саги
            existing = db.query(ProcessedEvent).filter_by(
                id=event_id, consumer="saga"
            ).first()
            if existing:
                logger.info("saga_duplicate_ignored", order_id=order_id)
                await message.ack()
                return

            # 1. Находим заказ
            order = db.query(Order).filter(Order.id == order_id).first()
            if order:
                # 2. Отменяем заказ
                order.status = "cancelled"
                
                # 3. Возвращаем деньги (компенсация)
                user = db.query(User).filter(User.id == order.user_id).first()
                if user and order.item:
                    refund_amount = order.item.price * order.quantity
                    user.balance += refund_amount
                    logger.info(
                        "saga_compensated", 
                        order_id=order_id, 
                        refund=refund_amount,
                        new_balance=user.balance
                    )
                
                db.add(ProcessedEvent(id=event_id, consumer="saga"))
                db.commit()
        finally:
            db.close()
        await message.ack()
    except Exception:
        logger.exception("saga_message_failed")
        await message.nack(requeue=True)

async def main() -> None:
    setup_logging()
    configure_telemetry("sirius-saga")
    connection, channel = await connect_consumer()
    
    # Слушаем событие провала доставки!
    queue, exchange, dead_exchange = await declare_consumer_topology(
        channel, "saga", "delivery.failed"
    )
    
    await queue.consume(lambda message: process_message(message, exchange, dead_exchange))
    logger.info("saga_consumer_started", queue="saga_queue")
    try:
        await asyncio.Future()
    finally:
        await connection.close()

if __name__ == "__main__":
    asyncio.run(main())