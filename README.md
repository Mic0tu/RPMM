# Sirius.Food

Модульный монолит на FastAPI + SQLAlchemy + PostgreSQL + Redis + Celery.  
Сквозной пет-проект «Сириус.Еда»: Clean Architecture, безопасность, кеширование, фоновые задачи.

## Возможности

- **Clean Architecture** — модули `orders`, `users`, `menu`, `delivery`, `auth` разделены на `router` / `service` / `repository`
- **JWT** — access (15 мин) + refresh (7 дней), bcrypt-хеши паролей
- **RBAC** — роли `student`, `cook`, `courier`, `admin`
- **IDOR-защита** — проверка владельца объекта в Service-слое
- **Rate limiting** — Redis, лимит на `/auth/login`
- **Cache-Aside** — меню в Redis (TTL 5 мин), событийная инвалидация, защита от cache stampede, warm-up при старте
- **Celery** — PDF / email / SMS в фоне, ретраи, идемпотентность, DLQ, Flower

## Архитектура

| Слой | Файл | Модель Мартина | Ответственность |
|------|------|----------------|-----------------|
| API Layer | `router.py` | Frameworks & Drivers | HTTP, Pydantic, HTTP-статусы |
| Business Logic | `service.py` | Entities + Use Cases | Бизнес-правила, оркестрация |
| Infrastructure | `repository.py` | Interface Adapters | SQL/ORM, Redis-кеш |

**Правила:**
- в `service.py` нет импортов `fastapi` и `sqlalchemy`
- репозиторий внедряется через конструктор (DIP)
- кеш и Celery вызываются так, чтобы бизнес-логика оставалась переиспользуемой

```
app/modules/<module>/
├── router.py
├── service.py
├── repository.py
└── exceptions.py   # при необходимости
```

### Путь запроса

```
HTTP → router (валидация, Depends) → service (правила) → repository (SQL / Redis) → PostgreSQL
```

```mermaid
sequenceDiagram
    participant Client
    participant Router as router.py
    participant Service as service.py
    participant Repo as repository.py
    participant DB as PostgreSQL

    Client->>Router: POST /orders/create
    Router->>Router: quantity > 0, JWT → user_id
    Router->>Service: create_order(...)
    Service->>Repo: get_user / get_item
    Repo->>DB: SELECT
    Service->>Service: баланс, доступность
    Service->>Repo: save_order, update_balance
    Repo->>DB: INSERT / UPDATE
    Service->>Service: Celery .delay() PDF/email/SMS
    Service-->>Router: order_id
    Router-->>Client: 200 {order_id}
```

### Безопасность

```mermaid
flowchart TD
    Client -->|Bearer JWT| Router
    Router --> Deps[get_current_user / require_role]
    Deps -->|ok| Service
    Deps -->|нет токена| HTTP401
    Deps -->|не та роль| HTTP403
    Service -->|order.user_id == current_user.id| Repo
    Service -->|чужой объект| AccessDenied
```

## Структура проекта

```
app/
├── core/
│   ├── config.py          # Settings из .env
│   ├── jwt.py
│   ├── security.py        # bcrypt
│   ├── dependencies.py    # get_current_user, require_role
│   ├── rate_limit.py
│   ├── redis.py
│   └── celery_app.py
├── modules/
│   ├── auth/
│   ├── users/
│   ├── menu/              # Cache-Aside в repository
│   ├── orders/            # Celery .delay() в service
│   └── delivery/
├── tasks/
│   └── orders.py          # PDF, email, SMS
├── tests/
├── main.py
├── models.py
├── schemas.py
└── database.py
```

## Запуск

```bash
python3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

docker compose up -d db redis

$env:PYTHONPATH = "."
alembic upgrade head          # из корня проекта (alembic.ini)

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# отдельные терминалы
celery -A app.core.celery_app worker --loglevel=info
celery -A app.core.celery_app flower --port=5555   # http://localhost:5555
```

Swagger: http://127.0.0.1:8000/docs (при `DEBUG=True` в `.env`).

### Быстрая проверка API

1. `POST /users/register` — `{ "email", "password", "phone?" }`
2. `POST /auth/login` — получить `access_token`
3. `POST /orders/create` — Header `Authorization: Bearer …`, body `{ "item_id", "quantity" }`
4. `GET /menu/items` — публичный, данные из Redis после первого запроса
5. `POST /menu/items` — только роль `cook`
6. `POST /orders/{id}/cancel` — только владелец заказа

### Нагрузочный тест меню

```bash
locust -f locustfile.py --host=http://127.0.0.1:8000
# UI: http://localhost:8089 → 500 users, spawn rate 10
```

## Кеширование меню

- Стратегия **Cache-Aside** в `MenuRepository.get_all`
- Ключ `menu:all`, TTL **300 с**
- Hit → Redis; miss → PostgreSQL → `setex`
- **Stampede protection**: `redis.lock("lock:menu:all")` + double-check
- Инвалидация при `create_item` / `update_item`
- **Warm-up** на `startup` в `main.py`
- Service не импортирует Redis

**50 одновременных пользователей, spawn 10/с, 15 с** — чистый эффект кеша:

| Метрика | До кеша | С Cache-Aside | Эффект |
|---|---|---|---|
| Среднее время ответа | 15 мс | **7 мс** | −53% |
| Медиана | 10 мс | **6 мс** | −40% |
| 95-й перцентиль | 41 мс | **19 мс** | −54% |
| 99-й перцентиль | 130 мс | **27 мс** | −79% |
| RPS | 134 | **140** | +5% |

**500 пользователей (пик из методички), spawn 10/с, 70 с:**

| Метрика | До кеша | С Cache-Aside | Эффект |
|---|---|---|---|
| Среднее время ответа | 338 мс | **287 мс** | −15% |
| Медиана | 330 мс | 270 мс | −18% |
| RPS | 486 | **543** | +12% |

## Фоновые задачи (Celery)

После `create_order` клиент получает ответ сразу; в очереди:

| Задача | Особенности |
|--------|-------------|
| `generate_order_pdf` | sleep 2с, идемпотентность (`pdf_generated:{id}` в Redis) |
| `send_order_email` | sleep 1с, autoretry + exponential backoff, max 3; падение при `order_id % 5 == 0` |
| `send_order_sms` | sleep 1с, retries; пропуск без телефона |

Очереди: `default`, `dlq`. Мониторинг: Flower `:5555`.

| Метрика | Синхронно | С Celery |
|---------|-----------|----------|
| Время ответа POST /orders/create | ~4–5 с | ~50–100 мс |

Проверка идемпотентности:

```bash
celery -A app.core.celery_app call app.tasks.orders.generate_order_pdf --args='[42]'
celery -A app.core.celery_app call app.tasks.orders.generate_order_pdf --args='[42]'
# второй вызов: "PDF already generated for order 42"
```

## Тесты

```bash
export PYTHONPATH=.
pytest app/tests/ -v
```

- `test_orders.py` — unit-тесты `OrderService` (мок репозитория и Celery, без БД)
- `test_security.py` — 401 без токена, 403 роль/IDOR, 429 rate limit

## Переменные окружения (`.env`)

```
SECRET_KEY=...
DATABASE_URL=postgresql://sirius:sirius@localhost:5432/sirius_food
REDIS_URL=redis://localhost:6379
DEBUG=True
ALLOWED_ORIGINS=["http://127.0.0.1:8000","http://localhost:8000"]
```

В продакшене: `DEBUG=False` (Swagger отключён), ограниченные `ALLOWED_ORIGINS`.


### gRPC и вынос delivery

- Контракт: `proto/delivery.proto`
- Сгенерированные bindings: `delivery_pb2.py`, `delivery_pb2_grpc.py`
- Микросервис: `delivery_server.py`, порт `50051`
- Клиент монолита: `app/modules/delivery/grpc_client.py`
- REST-эндпоинты монолита делегируют delivery через gRPC
- Таймауты и сетевые ошибки мапятся в `503/504/502`
- Реализованы unary-вызовы, server streaming `TrackDelivery` и bidirectional streaming `ChatWithCourier`

Запуск:

```bash
python -m grpc_tools.protoc -Iproto --python_out=. --grpc_python_out=. proto/delivery.proto
python delivery_server.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Дополнительная проверка: `GET /delivery/track/{order_id}` возвращает поток статусов в виде JSON-массивa.


http://localhost:15672


# Отчет по ЛР №8 (SSR vs CSR)

## Сравнительная таблица

| Метрика | SSR: `/menu` | CSR: `/menu-csr` |
| :--- | :--- | :--- |
| **Данные в Ctrl+U** | есть | нет |
| **Первый контент** | сразу | после загрузки JS |
| **Запрос к API из браузера** | нет | есть |
| **Время загрузки (ср. из 3 замеров)** | ~ 50 ms | ~ 400 ms |

## Выводы
При использовании SSR (Server-Side Rendering) сервер Next.js сразу отдает готовый HTML с данными, полученными из FastAPI. Это обеспечивает быструю первую загрузку и хорошую индексацию поисковиками.
При использовании CSR (Client-Side Rendering) браузер сначала получает пустой HTML, затем скачивает JavaScript, и только после этого делает запрос к API за данными. Это приводит к увеличению времени до первого контента и ухудшению SEO.