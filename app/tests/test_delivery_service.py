"""Unit-тесты DeliveryService без БД."""
from unittest.mock import MagicMock

import pytest

from app.modules.delivery.exceptions import (
    AccessDeniedError,
    BusinessRuleError,
    CourierNotFoundError,
    DeliveryNotFoundError,
    OrderNotFoundError,
)
from app.modules.delivery.service import DeliveryService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo):
    return DeliveryService(repository=mock_repo)


def test_assign_success(service, mock_repo):
    order = MagicMock()
    order.status = "paid"
    courier = MagicMock()
    courier.is_blocked = False
    delivery = MagicMock()
    delivery.id = 15

    mock_repo.get_order_by_id.return_value = order
    mock_repo.get_user_by_id.return_value = courier
    mock_repo.get_active_delivery_by_courier.return_value = None
    mock_repo.save_delivery.return_value = delivery

    assert service.assign_courier(1, 2) == 15


def test_assign_order_not_paid(service, mock_repo):
    order = MagicMock()
    order.status = "processing"
    mock_repo.get_order_by_id.return_value = order
    with pytest.raises(BusinessRuleError, match="оплаченный"):
        service.assign_courier(1, 2)


def test_assign_order_missing(service, mock_repo):
    mock_repo.get_order_by_id.return_value = None
    with pytest.raises(OrderNotFoundError):
        service.assign_courier(1, 2)


def test_assign_courier_blocked(service, mock_repo):
    order = MagicMock()
    order.status = "paid"
    courier = MagicMock()
    courier.is_blocked = True
    mock_repo.get_order_by_id.return_value = order
    mock_repo.get_user_by_id.return_value = courier
    with pytest.raises(AccessDeniedError):
        service.assign_courier(1, 2)


def test_assign_courier_busy(service, mock_repo):
    order = MagicMock()
    order.status = "paid"
    courier = MagicMock()
    courier.is_blocked = False
    mock_repo.get_order_by_id.return_value = order
    mock_repo.get_user_by_id.return_value = courier
    mock_repo.get_active_delivery_by_courier.return_value = MagicMock()
    with pytest.raises(BusinessRuleError, match="активная доставка"):
        service.assign_courier(1, 2)


def test_complete_success(service, mock_repo):
    delivery = MagicMock()
    delivery.status = "in_progress"
    delivery.order_id = 5
    order = MagicMock()
    mock_repo.get_delivery_by_id.return_value = delivery
    mock_repo.get_order_by_id.return_value = order

    service.complete_delivery(1)

    assert delivery.status == "completed"
    assert order.status == "delivered"


def test_complete_not_found(service, mock_repo):
    mock_repo.get_delivery_by_id.return_value = None
    with pytest.raises(DeliveryNotFoundError):
        service.complete_delivery(99)
