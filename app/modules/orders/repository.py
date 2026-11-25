"""
Инфраструктурный слой модуля заказов.
Только SQL / ORM, без бизнес-правил.
"""
from datetime import datetime
import json
import uuid

from sqlalchemy.orm import Session

from app.models import MenuItem, Order, OutboxEvent, ProcessedEvent, User


class OrderRepository:
    """
    Класс отвечает исключительно за выполнение операций ввода-вывода
    в контексте СУБД PostgreSQL с использованием SQLAlchemy ORM.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_menu_item_by_id(self, item_id: int) -> MenuItem | None:
        return self.db.query(MenuItem).filter(MenuItem.id == item_id).first()

    def save_order(self, user_id: int, item_id: int, quantity: int) -> int:
        """Создание заказа. Возвращает id."""
        new_order = Order(
            user_id=user_id,
            item_id=item_id,
            quantity=quantity,
            status="processing",
        )
        self.db.add(new_order)
        self.db.commit()
        self.db.refresh(new_order)
        return new_order.id

    def update_user_balance(self, user: User, new_balance: float) -> None:
        user.balance = new_balance
        self.db.add(user)
        self.db.commit()

    def get_order_by_id(self, order_id: int) -> Order | None:
        return self.db.query(Order).filter(Order.id == order_id).first()

    def get_order(self, order_id: int) -> Order | None:
        return self.get_order_by_id(order_id)

    def get_menu_item(self, item_id: int) -> MenuItem | None:
        return self.get_menu_item_by_id(item_id)

    def pay_order_and_enqueue(
        self, order_id: int, user_id: int, correlation_id: str, trace_context: str = "{}"
    ) -> Order | None:
        """Mark the order paid and persist its event in one database transaction."""
        order = (
            self.db.query(Order)
            .filter(Order.id == order_id)
            .with_for_update()
            .first()
        )
        if order is None:
            return None
        if order.user_id != user_id:
            return None
        if order.status == "paid":
            return order
        if order.status != "processing":
            return None
        item = self.get_menu_item_by_id(order.item_id)
        amount = float(item.price) * order.quantity if item else 0.0
        event_id = str(uuid.uuid4())
        payload = {
            "event_id": event_id,
            "order_id": order.id,
            "customer_id": order.user_id,
            "amount": amount,
        }
        order.status = "paid"
        self.db.add(order)
        self.db.add(OutboxEvent(
            id=event_id,
            routing_key="order.paid",
            payload=json.dumps(payload),
            correlation_id=correlation_id,
            trace_context=trace_context,
        ))
        self.db.commit()
        self.db.refresh(order)
        return order

    def pending_outbox(self, limit: int = 100) -> list[OutboxEvent]:
        return (
            self.db.query(OutboxEvent)
            .filter(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.created_at)
            .with_for_update(skip_locked=True)
            .limit(limit)
            .all()
        )

    def mark_outbox_published(self, event: OutboxEvent) -> None:
        event.published_at = datetime.utcnow()
        event.last_error = None
        self.db.add(event)
        self.db.commit()

    def mark_outbox_failed(self, event: OutboxEvent, error: str) -> None:
        event.attempts += 1
        event.last_error = error[:2000]
        self.db.add(event)
        self.db.commit()

    def compensate_failed_delivery(
        self, order_id: int, event_id: str, correlation_id: str = "unknown"
    ) -> bool:
        """Refund exactly once and cancel the order when delivery assignment fails."""
        processed = self.db.query(ProcessedEvent).filter_by(
            id=event_id, consumer="order_saga"
        ).first()
        if processed:
            return False
        order = self.get_order_by_id(order_id)
        if order is None:
            self.db.add(ProcessedEvent(id=event_id, consumer="order_saga"))
            self.db.commit()
            return False
        user = self.get_user_by_id(order.user_id)
        item = self.get_menu_item_by_id(order.item_id)
        refunded_amount = 0.0
        if order.status != "cancelled" and user and item:
            refunded_amount = float(item.price) * order.quantity
            user.balance += refunded_amount
            order.status = "cancelled"
            self.db.add(user)
            self.db.add(order)
        self.db.add(ProcessedEvent(id=event_id, consumer="order_saga"))
        cancelled_event_id = str(uuid.uuid4())
        self.db.add(OutboxEvent(
            id=cancelled_event_id,
            routing_key="order.cancelled",
            payload=json.dumps({
                "event_id": cancelled_event_id,
                "order_id": order_id,
                "refund_amount": refunded_amount,
                "reason": "delivery_assignment_failed",
            }),
            correlation_id=correlation_id,
        ))
        self.db.commit()
        return True

    def mark_event_processed(self, event_id: str, consumer: str) -> bool:
        """Store the consumer-specific idempotency key in its own transaction."""
        existing = self.db.query(ProcessedEvent).filter_by(
            id=event_id, consumer=consumer
        ).first()
        if existing:
            return False
        self.db.add(ProcessedEvent(id=event_id, consumer=consumer))
        self.db.commit()
        return True

    def update_order(self, order: Order) -> None:
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)

    def get_orders_by_status(self, status: str) -> list[Order]:
        return self.db.query(Order).filter(Order.status == status).all()

