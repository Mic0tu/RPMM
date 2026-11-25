from fastapi import APIRouter, Depends, Header, HTTPException
from app.models import User
from app.modules.orders.exceptions import AccessDeniedError, OrderNotFoundError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.database import get_db
from app.modules.orders.repository import OrderRepository
from app.modules.orders.service import OrderService
from app.schemas import OrderCreate

import structlog
from fastapi import Request

logger = structlog.get_logger()

router = APIRouter()


@router.post("/{order_id}/pay")
def pay_order(
    order_id: int,
    request: Request,
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Оплатить заказ и атомарно записать OrderPaid в transactional outbox."""
    service = OrderService(OrderRepository(db))
    try:
        order = service.pay_order(
            order_id=order_id,
            current_user=current_user,
            correlation_id=request.state.correlation_id,
        )
    except OrderNotFoundError:
        raise HTTPException(status_code=404, detail="Order not found")
    except AccessDeniedError:
        raise HTTPException(status_code=403, detail="Access denied")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    logger.info(
        "order_paid",
        order_id=order.id,
        user_id=current_user.id,
        correlation_id=request.state.correlation_id,
    )
    return {"status": "paid", "order_id": order.id}


@router.post("/create")
def create_order(
    request: Request,
    payload: OrderCreate,
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    correlation_id = request.state.correlation_id
    
    # Техническая валидация уровня транспортного протокола.
    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="Количество должно быть больше нуля")

    # Сборка архитектурных слоёв.
    repository = OrderRepository(db)
    service = OrderService(repository)

    # Делегирование выполнения сценария слою бизнес-логики.
    try:
        order_id = service.create_order(
            user_id=current_user.id,
            item_id=payload.item_id,
            quantity=payload.quantity,
        )
    except ValueError as e:
        # Трансляция внутреннего исключения в HTTP-статус.
        raise HTTPException(status_code=400, detail=str(e))

    logger.info(
        "order_created",
        order_id=order_id,
        user_id=current_user.id,
        correlation_id=correlation_id,
    )

    return {"status": "success", "order_id": order_id}


@router.post("/{order_id}/cancel")
def cancel_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = OrderRepository(db)
    service = OrderService(repository)
    try:
        service.cancel_order(order_id, current_user)
    except OrderNotFoundError:
        raise HTTPException(404, "Order not found")
    except AccessDeniedError:
        raise HTTPException(403, "Access denied")
    return {"status": "success"}



@router.get("/kitchen/orders")
def kitchen_orders(
    current_user: User = Depends(require_role("cook")),
    db: Session = Depends(get_db),
):
    repository = OrderRepository(db)
    service = OrderService(repository)
    return service.get_kitchen_orders()
