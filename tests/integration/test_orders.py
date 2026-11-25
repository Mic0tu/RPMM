
import pytest

from app.models import User, MenuItem, Order
from app.core.dependencies import get_current_user
from app.main import app


def test_create_order_saves_to_db(client, db, monkeypatch):
    """Проверяет, что POST /orders/create сохраняет заказ в БД."""

    # 1. Создаём тестового пользователя и блюдо.
    user = User(
        email="test@example.com",
        balance=1000.0,
        password_hash="fake",
    )
    item = MenuItem(
        name="Сырники",
        price=150.0,
        is_available=True,
    )

    db.add_all([user, item])
    db.commit()
    db.refresh(user)
    db.refresh(item)

    # 2. Подменяем авторизацию.
    app.dependency_overrides[get_current_user] = lambda: user

    # 3. Отключаем отправку фоновых задач Celery.
    # Проверяем PostgreSQL, поэтому Redis для этого теста не нужен.
    from app.tasks import orders as order_tasks

    monkeypatch.setattr(
        order_tasks.generate_order_pdf,
        "delay",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        order_tasks.send_order_email,
        "delay",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        order_tasks.send_order_sms,
        "delay",
        lambda *args, **kwargs: None,
    )

    try:
        # 4. Отправляем запрос.
        response = client.post(
            "/orders/create",
            json={
                "item_id": item.id,
                "quantity": 2,
            },
        )

        # 5. Проверяем ответ API.
        assert response.status_code == 200, (
            f"Ошибка API: {response.json()}"
        )

        order_id = response.json()["order_id"]

        # 6. Проверяем, что заказ действительно появился в БД.
        order = db.query(Order).filter_by(id=order_id).first()

        assert order is not None
        assert order.quantity == 2

    finally:
        # 7. Убираем подмену авторизации.
        app.dependency_overrides.clear()
