"""
Слой бизнес-логики модуля доставки.
Не импортирует fastapi и sqlalchemy.
"""
from app.models import Delivery, User
from app.modules.delivery.exceptions import (
    AccessDeniedError,
    BusinessRuleError,
    CourierNotFoundError,
    DeliveryNotFoundError,
    OrderNotFoundError,
)
from app.modules.delivery.repository import DeliveryRepository
from app.modules.delivery.grpc_client import DeliveryGrpcClient


class DeliveryService:
    def __init__(self, repository: DeliveryRepository):
        self.repository = repository
        self.client = DeliveryGrpcClient()

    def assign_courier(self, order_id: int, courier_id: int) -> int:
        """
        Назначает курьера на заказ.
        Возвращает id созданной доставки.
        """
        order = self.repository.get_order_by_id(order_id)
        if not order:
            raise OrderNotFoundError()

        # Бизнес-правило: курьера можно назначить только на оплаченный заказ
        if order.status != "paid":
            raise BusinessRuleError("Курьера можно назначить только на оплаченный заказ")

        # courier = self.repository.get_user_by_id(courier_id)
        courier = self.repository.get_user_by_id(courier_id)
        if not courier:
            raise CourierNotFoundError()

        if courier.is_blocked:
            raise AccessDeniedError("Курьер заблокирован и не может быть назначен")

        # Бизнес-правило: один курьер — одна активная доставка
        active = self.repository.get_active_delivery_by_courier(courier_id)
        if active:
            raise BusinessRuleError("У курьера уже есть активная доставка")

        # delivery = self.repository.save_delivery(
        #     order_id=order_id,
        #     courier_id=courier_id,
        #     status="in_progress",
        # )
        delivery = self.client.assign_courier(order_id=order_id, courier_id=courier_id)
        # return delivery.id
        return delivery["id"]

    def complete_delivery(self, delivery_id: int) -> None:
        """Завершает доставку и обновляет статус заказа."""
        delivery = self.repository.get_delivery_by_id(delivery_id)
        if not delivery:
            raise DeliveryNotFoundError()

        if delivery.status == "completed":
            raise BusinessRuleError("Доставка уже завершена")

        if delivery.status == "cancelled":
            raise BusinessRuleError("Отменённую доставку нельзя завершить")

        self.client.complete_delivery(delivery_id=delivery_id)
        delivery.status = "completed"
        self.repository.update_delivery(delivery)

        order = self.repository.get_order_by_id(delivery.order_id)
        if order:
            order.status = "delivered"
            self.repository.update_order(order)
