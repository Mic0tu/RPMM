import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.redis import redis_client
from app.models import MenuItem


class MenuRepository:
    def __init__(self, db: Session):
        self.db = db

    def _serialize_items(self, items: list[MenuItem]) -> str:
        """Сериализация списка MenuItem в JSON для Redis."""
        return json.dumps(
            [
                {
                    "id": i.id,
                    "name": i.name,
                    "price": i.price,
                    "is_available": i.is_available,
                }
                for i in items
            ]
        )

    def _deserialize_items(self, data: str) -> list[MenuItem]:
        """Восстановление объектов MenuItem из JSON-кеша."""
        items_data: list[dict[str, Any]] = json.loads(data)
        return [MenuItem(**item) for item in items_data]

    def get_all(self) -> list[MenuItem]:
        """
        Возвращает всё меню.
        Стратегия Cache-Aside + защита от cache stampede через Redis Lock.

        1. Проверяем кеш.
        2. При hit — возвращаем.
        3. При miss — берём distributed lock, double-check, идём в БД,
           кладём в кеш и освобождаем lock.
        """

        cache_key = "menu:all"
        lock_key = "lock:menu:all"

        # 1. Быстрая проверка кеша (без блокировки)
        cached_data = redis_client.get(cache_key)
        if cached_data:
            return self._deserialize_items(cached_data)
        
        # 2. Cache miss — защита от stampede
        # Только один процесс/воркер пойдёт в БД, остальные ждут.
        lock = redis_client.lock(
            lock_key,
            timeout=10,           # максимальное время удержания лока
            blocking_timeout=5,   # сколько ждать получения лока
        )

        acquired = False
        try:
            acquired = lock.acquire(blocking=True)
            if acquired:
                # Double-check: пока ждали лок, кто-то мог уже заполнить кеш
                cached_data = redis_client.get(cache_key)
                if cached_data:
                    return self._deserialize_items(cached_data)

                # Реальный miss — идём в БД
                items = self.db.query(MenuItem).all()

                # Сохраняем в кеш с TTL 5 минут (300 секунд)
                redis_client.setex(cache_key, 300, self._serialize_items(items))
                return items
            else:
                # Не удалось получить лок — пробуем ещё раз прочитать кеш
                # (возможно, другой воркер уже успел)
                cached_data = redis_client.get(cache_key)
                if cached_data:
                    return self._deserialize_items(cached_data)

                # Fallback: идём в БД без лока (лучше отдать данные, чем ошибку)
                items = self.db.query(MenuItem).all()
                return items
        finally:
            if acquired:
                try:
                    lock.release()
                except Exception:
                    # Лок мог уже истечь по timeout — игнорируем
                    pass

    def get_by_name(self, name: str) -> MenuItem | None:
        return self.db.query(MenuItem).filter(MenuItem.name == name).first()

    def get_by_id(self, item_id: int) -> MenuItem | None:
        return self.db.query(MenuItem).filter(MenuItem.id == item_id).first()

    def save(self, name: str, price: float) -> MenuItem:
        new_item = MenuItem(
            name=name,
            price=price,
            is_available=True,
        )
        self.db.add(new_item)
        self.db.commit()
        self.db.refresh(new_item)
        return new_item

    def update(self, item: MenuItem) -> None:
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)

    def invalidate_cache(self) -> None:
        """Событийная инвалидация: сбрасывает кеш меню при изменении данных."""
        redis_client.delete("menu:all")
        # Также снимаем возможный лок, чтобы не блокировать следующие запросы
        redis_client.delete("lock:menu:all")
