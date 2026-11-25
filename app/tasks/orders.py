"""
Фоновые задачи для модуля заказов.
Имитация тяжёлых операций (PDF, email, SMS) + ретраи, идемпотентность.
"""
import time

from app.core.celery_app import celery_app
from app.core.redis import redis_client

# настройка очередей
@celery_app.task(
    bind=True,
    name="app.tasks.orders.generate_order_pdf",
)
def generate_order_pdf(self, order_id: int) -> str:
    """
    Генерация PDF-чека для заказа.
    Идемпотентность: повторный запуск не создаёт дубль.
    """
    key = f"pdf_generated:{order_id}"

    # Если ключ уже есть — PDF уже сгенерирован, пропускаем
    if redis_client.exists(key):
        return f"PDF already generated for order {order_id}"

    # Имитация тяжёлой операции
    time.sleep(2)

    # Сохраняем флаг на 1 час
    redis_client.setex(key, 3600, "1")
    return f"PDF generated for order {order_id}"


@celery_app.task(
    bind=True,
    name="app.tasks.orders.send_order_email",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def send_order_email(self, order_id: int, email: str) -> str:
    """
    Отправка email о создании заказа.
    Ретраи с экспоненциальной задержкой (1с → 2с → 4с).
    Имитация падения для order_id % 5 == 0 (для демонстрации ретраев).
    """
    time.sleep(1)

    # Имитация временной недоступности внешнего сервиса
    if order_id % 5 == 0:
        raise Exception("Email service unavailable")

    return f"Email sent to {email} for order {order_id}"


@celery_app.task(
    bind=True,
    name="app.tasks.orders.send_order_sms",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def send_order_sms(self, order_id: int, phone: str | None) -> str:
    """Отправка SMS о создании заказа."""
    if not phone:
        return f"SMS skipped for order {order_id}: no phone"

    time.sleep(1)
    return f"SMS sent to {phone} for order {order_id}"
