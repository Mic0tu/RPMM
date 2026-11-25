from app.models import User, MenuItem, Order
from app.core.dependencies import get_current_user # <--- Импортируем твою защиту
from app.main import app
from app.modules.orders import service

def test_create_order_saves_to_db(client, db, monkeypatch):
    """Проверяет, что POST /orders/create сохраняет заказ в БД."""
    
    # 1. Создаем тестового пользователя и блюдо
    user = User(email="test@example.com", balance=1000.0, password_hash="fake")
    item = MenuItem(name="Сырники", price=150.0, is_available=True)
    db.add_all([user, item])
    db.commit()

    # 2. ОБХОДИМ АВТОРИЗАЦИЮ (Магия тестирования)
    # Говорим FastAPI: "Для этого теста считай, что запрос делает наш user"
    app.dependency_overrides[get_current_user] = lambda: user

    # Отключаем отправку фоновой задачи Celery.
    # В этом тесте проверяем PostgreSQL, а не генерацию PDF.
    monkeypatch.setattr(
    service.generate_order_pdf,
    "delay",
    lambda *args, **kwargs: None
    )

    # 3. Отправляем запрос (без user_id, так как мы его убрали в 3-й лабе)
    response = client.post("/orders/create", json={
        "item_id": item.id,
        "quantity": 2,
    })

    # 4. Проверяем ответ API
    assert response.status_code == 200, f"Ошибка API: {response.json()}"
    order_id = response.json()["order_id"]

    # 5. Проверяем, что заказ реально появился в БД
    order = db.query(Order).filter_by(id=order_id).first()
    assert order is not None
    assert order.quantity == 2
    
    # 6. Убираем подмену, чтобы не сломать другие тесты
    app.dependency_overrides.clear()