"""
Слой бизнес-логики модуля заказов.
Вызов фоновых задач Celery — часть сценария «после заказа уведомить».
Service не импортирует FastAPI и SQLAlchemy.
"""
import json

from opentelemetry import propagate

from app.models import User
from app.modules.orders.exceptions import AccessDeniedError, OrderNotFoundError
from app.modules.orders.repository import OrderRepository
from app.models import Order


class OrderService:
    """
    Бизнес-правила заказов.
    Репозиторий внедряется через конструктор (DIP).
    """

    def __init__(self, repository: OrderRepository):
        self.repository = repository

    def create_order(self, user_id: int, item_id: int, quantity: int) -> int:
        """
        Оформление заказа. Тяжёлые операции (PDF, email, SMS) — в фоне.
        Возвращает id заказа. При нарушении правил — ValueError.
        """
        user = self.repository.get_user_by_id(user_id)
        if not user:
            raise ValueError("Пользователь не найден")

        item = self.repository.get_menu_item_by_id(item_id)
        if not item:
            raise ValueError("Указанное блюдо не найдено в меню")

        if not item.is_available:
            raise ValueError("Блюдо временно недоступно")

        total_cost = item.price * quantity
        if user.balance < total_cost:
            raise ValueError("Недостаточно средств на балансе студента")

        user.balance -= total_cost
        self.repository.update_user_balance(user, user.balance)

        order_id = self.repository.save_order(user_id, item_id, quantity)

        # Фоновые задачи: .delay() не блокирует ответ клиенту
        self._enqueue_notifications(order_id, user.email, user.phone)

        return order_id

    def _enqueue_notifications(
        self, order_id: int, email: str | None, phone: str | None
    ) -> None:
        """Ставит PDF / email / SMS в очередь Celery. Вынесено для удобства тестов."""
        from app.tasks.orders import (
            generate_order_pdf,
            send_order_email,
            send_order_sms,
        )

        generate_order_pdf.delay(order_id)
        send_order_email.delay(order_id, email)
        send_order_sms.delay(order_id, phone)

    def cancel_order(self, order_id: int, current_user: User) -> None:
        """Отмена заказа только владельцем (защита от IDOR)."""
        order = self.repository.get_order_by_id(order_id)
        if order is None:
            raise OrderNotFoundError()
        if order.user_id != current_user.id:
            raise AccessDeniedError()
        order.status = "cancelled"
        self.repository.update_order(order)

    def get_kitchen_orders(self) -> list[dict]:
        """Заказы со статусом processing (для кухни)."""
        orders = self.repository.get_orders_by_status("processing")
        return [
            {
                "id": o.id,
                "user_id": o.user_id,
                "item_id": o.item_id,
                "quantity": o.quantity,
                "status": o.status,
            }
            for o in orders
        ]

    def pay_order(self, order_id: int, current_user: User, correlation_id: str) -> Order:
        """
        Оплата заказа. Outbox-событие сохраняется в той же транзакции.
        """
        order = self.repository.get_order(order_id)
        if not order:
            raise OrderNotFoundError()
        if order.user_id != current_user.id:
            raise AccessDeniedError()
        if order.status == "paid":
            return order
        if order.status != "processing":
            raise ValueError("Нельзя оплатить заказ в текущем статусе")
        trace_context: dict[str, str] = {}
        propagate.inject(trace_context)
        paid_order = self.repository.pay_order_and_enqueue(
            order_id=order_id,
            user_id=current_user.id,
            correlation_id=correlation_id,
            trace_context=json.dumps(trace_context),
        )
        if not paid_order:
            raise OrderNotFoundError()
        return paid_order
