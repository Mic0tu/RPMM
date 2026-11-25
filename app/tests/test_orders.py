"""
Unit-тесты OrderService без СУБД и без Celery-воркера.
Репозиторий и постановка задач в очередь — моки.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.orders.exceptions import AccessDeniedError, OrderNotFoundError
from app.modules.orders.service import OrderService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo):
    return OrderService(repository=mock_repo)


@patch.object(OrderService, "_enqueue_notifications")
def test_create_order_success(mock_enqueue, service, mock_repo):
    user = MagicMock()
    user.balance = 1000.0
    user.email = "student@test.ru"
    user.phone = "+79001234567"

    item = MagicMock()
    item.price = 250.0
    item.is_available = True

    mock_repo.get_user_by_id.return_value = user
    mock_repo.get_menu_item_by_id.return_value = item
    mock_repo.save_order.return_value = 42

    order_id = service.create_order(user_id=1, item_id=10, quantity=2)

    assert order_id == 42
    assert user.balance == 500.0
    mock_repo.get_user_by_id.assert_called_once_with(1)
    mock_repo.get_menu_item_by_id.assert_called_once_with(10)
    mock_repo.update_user_balance.assert_called_once_with(user, 500.0)
    mock_repo.save_order.assert_called_once_with(1, 10, 2)
    mock_enqueue.assert_called_once_with(42, "student@test.ru", "+79001234567")


def test_create_order_user_not_found(service, mock_repo):
    mock_repo.get_user_by_id.return_value = None
    with pytest.raises(ValueError, match="Пользователь не найден"):
        service.create_order(user_id=999, item_id=1, quantity=1)


def test_create_order_item_not_found(service, mock_repo):
    mock_repo.get_user_by_id.return_value = MagicMock(balance=1000)
    mock_repo.get_menu_item_by_id.return_value = None
    with pytest.raises(ValueError, match="Указанное блюдо не найдено в меню"):
        service.create_order(user_id=1, item_id=999, quantity=1)


def test_create_order_insufficient_balance(service, mock_repo):
    user = MagicMock()
    user.balance = 100.0
    item = MagicMock()
    item.price = 200.0
    item.is_available = True
    mock_repo.get_user_by_id.return_value = user
    mock_repo.get_menu_item_by_id.return_value = item
    with pytest.raises(ValueError, match="Недостаточно средств на балансе студента"):
        service.create_order(user_id=1, item_id=3, quantity=1)


def test_create_order_item_unavailable(service, mock_repo):
    user = MagicMock()
    user.balance = 1000.0
    item = MagicMock()
    item.price = 100.0
    item.is_available = False
    mock_repo.get_user_by_id.return_value = user
    mock_repo.get_menu_item_by_id.return_value = item
    with pytest.raises(ValueError, match="Блюдо временно недоступно"):
        service.create_order(user_id=1, item_id=1, quantity=1)


def test_cancel_order_success(service, mock_repo):
    order = MagicMock()
    order.user_id = 1
    order.status = "processing"
    mock_repo.get_order_by_id.return_value = order
    current_user = MagicMock()
    current_user.id = 1

    service.cancel_order(10, current_user)

    assert order.status == "cancelled"
    mock_repo.update_order.assert_called_once_with(order)


def test_cancel_order_not_found(service, mock_repo):
    mock_repo.get_order_by_id.return_value = None
    with pytest.raises(OrderNotFoundError):
        service.cancel_order(99, MagicMock(id=1))


def test_cancel_order_idor(service, mock_repo):
    """Чужой заказ → AccessDeniedError (IDOR-защита в Service)."""
    order = MagicMock()
    order.user_id = 2
    mock_repo.get_order_by_id.return_value = order
    with pytest.raises(AccessDeniedError):
        service.cancel_order(10, MagicMock(id=1))


def test_get_kitchen_orders(service, mock_repo):
    o = MagicMock()
    o.id = 1
    o.user_id = 5
    o.item_id = 3
    o.quantity = 2
    o.status = "processing"
    mock_repo.get_orders_by_status.return_value = [o]

    result = service.get_kitchen_orders()

    assert result == [
        {"id": 1, "user_id": 5, "item_id": 3, "quantity": 2, "status": "processing"}
    ]
    mock_repo.get_orders_by_status.assert_called_once_with("processing")
