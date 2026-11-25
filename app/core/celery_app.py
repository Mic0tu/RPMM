"""
Конфигурация Celery для фоновых задач «Сириус.Еда».
Брокер и backend — Redis.
"""
from celery import Celery
from kombu import Exchange, Queue

from app.core.config import settings

# Создаём приложение Celery.
# Брокер (Redis) — сюда FastAPI ставит задачи.
# Backend (Redis) — сюда сохраняются результаты выполнения.
# Настройти celery
celery_app = Celery(
    "sirius_food",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.orders"],  # авто-импорт задач
)

# Настройки сериализации: JSON вместо pickle (безопаснее).
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Результат хранится 1 час
    result_expires=3600,
    # Задачи, упавшие после max_retries, помечаются как failed
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# Очереди: default + Dead Letter Queue
celery_app.conf.task_queues = (
    Queue("default", Exchange("default"), routing_key="default"),
    Queue("dlq", Exchange("dlq"), routing_key="dlq"),
)

celery_app.conf.task_default_queue = "default"
celery_app.conf.task_default_exchange = "default"
celery_app.conf.task_default_routing_key = "default"

# Для Flower / мониторинга
celery_app.conf.worker_send_task_events = True
celery_app.conf.task_send_sent_event = True
