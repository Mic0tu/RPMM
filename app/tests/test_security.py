"""
Тесты безопасности: 401 / 403 / IDOR / rate limit.
HTTP-тесты используют dependency_overrides — без реальной БД и Redis.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user, require_role
from app.core.jwt import create_access_token
from app.database import get_db
from app.main import app
from app.models import User
from app.modules.orders.exceptions import AccessDeniedError


client = TestClient(app)


def _make_user(user_id: int = 1, role_name: str = "student", is_blocked: bool = False):
    role = MagicMock()
    role.name = role_name
    user = MagicMock(spec=User)
    user.id = user_id
    user.email = f"user{user_id}@test.ru"
    user.is_blocked = is_blocked
    user.role = role
    user.role_id = 1
    return user


def _auth_header(user_id: int = 1) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def _fake_db():
    yield MagicMock()


@pytest.fixture(autouse=True)
def clear_overrides():
    """Сброс overrides после каждого теста."""
    yield
    app.dependency_overrides.clear()


# ---------- 1. Без токена → 401 ----------

def test_create_order_without_token():
    response = client.post("/orders/create", json={"item_id": 1, "quantity": 1})
    assert response.status_code == 401


def test_cancel_order_without_token():
    response = client.post("/orders/1/cancel")
    assert response.status_code == 401


# ---------- 2. Чужая роль → 403 ----------

def test_kitchen_orders_wrong_role():
    student = _make_user(1, "student")
    app.dependency_overrides[get_current_user] = lambda: student
    app.dependency_overrides[get_db] = _fake_db

    response = client.get("/orders/kitchen/orders", headers=_auth_header(1))
    assert response.status_code == 403


def test_menu_update_by_student():
    student = _make_user(1, "student")
    app.dependency_overrides[get_current_user] = lambda: student
    app.dependency_overrides[get_db] = _fake_db

    response = client.patch(
        "/menu/items/1",
        json={"price": 300},
        headers=_auth_header(1),
    )
    assert response.status_code == 403


def test_require_role_allows_matching_role():
    cook = _make_user(2, "cook")
    checker = require_role("cook")
    result = checker(current_user=cook)
    assert result.id == 2


def test_require_role_denies_other_role():
    student = _make_user(1, "student")
    checker = require_role("cook")
    with pytest.raises(HTTPException) as exc:
        checker(current_user=student)
    assert exc.value.status_code == 403


# ---------- 3. IDOR → 403 ----------

@patch("app.modules.orders.router.OrderService")
def test_cancel_foreign_order(mock_service_cls):
    student = _make_user(1, "student")
    app.dependency_overrides[get_current_user] = lambda: student
    app.dependency_overrides[get_db] = _fake_db

    instance = mock_service_cls.return_value
    instance.cancel_order.side_effect = AccessDeniedError()

    response = client.post("/orders/99/cancel", headers=_auth_header(1))
    assert response.status_code == 403


# ---------- 4. Rate limiting → 429 ----------

@patch("app.core.rate_limit.redis_client")
def test_login_rate_limit(mock_redis):
    mock_redis.incr.return_value = 6
    mock_redis.expire.return_value = True

    response = client.post(
        "/auth/login",
        json={"email": "test@test.ru", "password": "wrong"},
    )
    assert response.status_code == 429
    assert "Too many requests" in response.json()["detail"]
