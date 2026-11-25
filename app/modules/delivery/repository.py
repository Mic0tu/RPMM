"""
Инфраструктурный слой модуля доставки.
Только SQL / ORM, без бизнес-правил.
"""
from sqlalchemy.orm import Session

from app.models import Delivery, Order, User


class DeliveryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_order_by_id(self, order_id: int) -> Order | None:
        return self.db.query(Order).filter(Order.id == order_id).first()

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_delivery_by_id(self, delivery_id: int) -> Delivery | None:
        return self.db.query(Delivery).filter(Delivery.id == delivery_id).first()

    def get_active_delivery_by_courier(self, courier_id: int) -> Delivery | None:
        return (
            self.db.query(Delivery)
            .filter(
                Delivery.courier_id == courier_id,
                Delivery.status == "in_progress",
            )
            .first()
        )

    def save_delivery(self, order_id: int, courier_id: int, status: str = "in_progress") -> Delivery:
        new_delivery = Delivery(
            order_id=order_id,
            courier_id=courier_id,
            status=status,
        )
        self.db.add(new_delivery)
        self.db.commit()
        self.db.refresh(new_delivery)
        return new_delivery

    def update_delivery(self, delivery: Delivery) -> None:
        self.db.add(delivery)
        self.db.commit()
        self.db.refresh(delivery)

    def update_order(self, order: Order) -> None:
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
