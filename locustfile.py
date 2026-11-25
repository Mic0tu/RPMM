# locustfile.py
from locust import HttpUser, task, between

class SiriusUser(HttpUser):
    wait_time = between(1, 3) # Пауза между запросами 1-3 сек

    @task(7)
    def get_menu(self):
        """70% запросов — просмотр меню (тестируем Redis-кеш)"""
        self.client.get("/menu/items")

    @task(2)
    def get_menu_item(self):
        """20% запросов — карточка блюда"""
        self.client.get("/menu/items/1")

    @task(1)
    def create_order(self):
        """10% запросов — создание заказа (тестируем БД)"""
        # Если у тебя включена авторизация, добавь headers={"Authorization": "Bearer ..."}
        self.client.post("/orders/create", json={
            "user_id": 1,
            "item_id": 1,
            "quantity": 1,
        })