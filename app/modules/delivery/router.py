"""
Модуль управления доставкой.
Транспортный слой (API Layer).
"""
import uuid

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.database import get_db
from app.models import User
from app.modules.delivery.exceptions import (
    AccessDeniedError,
    BusinessRuleError,
    CourierNotFoundError,
    DeliveryNotFoundError,
    OrderNotFoundError,
)
from app.modules.delivery.repository import DeliveryRepository
from app.modules.delivery.service import DeliveryService
from app.schemas import DeliveryAssign
from app.core.rabbitmq import publish_event

router = APIRouter()
logger = structlog.get_logger()


@router.post("/assign")
async def assign_courier(
    payload: DeliveryAssign,
    request: Request,
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    repository = DeliveryRepository(db)
    service = DeliveryService(repository)

    try:
        delivery_id = service.assign_courier(
            order_id=payload.order_id,
            courier_id=payload.courier_id,
        )
    except OrderNotFoundError:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    except CourierNotFoundError:
        event_id = str(uuid.uuid4())
        correlation_id = str(request.state.correlation_id)
        await publish_event(
            "delivery.failed",
            {
                "event_id": event_id,
                "order_id": payload.order_id,
                "reason": "courier_not_found",
            },
            correlation_id,
        )
        logger.warning(
            "delivery_assignment_failed",
            order_id=payload.order_id,
            event_id=event_id,
            correlation_id=correlation_id,
        )
        raise HTTPException(status_code=404, detail="Курьер не найден")
    except AccessDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessRuleError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return {"status": "success", "delivery_id": delivery_id}


@router.patch("/{delivery_id}/complete")
def complete_delivery(
    delivery_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    repository = DeliveryRepository(db)
    service = DeliveryService(repository)

    try:
        service.complete_delivery(delivery_id)
    except DeliveryNotFoundError:
        raise HTTPException(status_code=404, detail="Доставка не найдена")
    except BusinessRuleError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return {"status": "success"}
