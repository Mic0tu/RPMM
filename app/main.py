"""
Точка входа приложения. Выполняет инициализацию FastAPI,
подключение модулей и создание таблиц базы данных.
"""
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.observability import configure_telemetry, instrument_fastapi

# 1. Настраиваем логи и OTel (до создания app)
setup_logging()
configure_telemetry("sirius-monolith")

from app.core.correlation import correlation_id_middleware
from app.modules.auth.router import router as auth_router
from app.modules.delivery.router import router as delivery_router
from app.modules.menu.router import router as menu_router
from app.modules.orders.router import router as orders_router
from app.modules.users.router import router as users_router

# 2. Создаем приложение
app = FastAPI(
    title="Sirius.Food API",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
)
logger = structlog.get_logger()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    # Убрали блок Sentry, оставили только логирование
    logger.exception(
        "unhandled_api_error",
        correlation_id=correlation_id,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "correlation_id": correlation_id},
        headers={"X-Correlation-ID": correlation_id},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(set(settings.ALLOWED_ORIGINS + [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ])),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Correlation-ID"],
    expose_headers=["X-Correlation-ID"],
)
app.middleware("http")(correlation_id_middleware)

app.include_router(auth_router, tags=["auth"])
app.include_router(users_router, prefix="/users", tags=["users"])
app.include_router(menu_router, prefix="/menu", tags=["menu"])
app.include_router(orders_router, prefix="/orders", tags=["orders"])
app.include_router(delivery_router, prefix="/delivery", tags=["delivery"])

# 3. Подключаем метрики и OTel уже к СОЗДАННОМУ приложению
Instrumentator().instrument(app).expose(app)
instrument_fastapi(app)


if settings.DEBUG:
    @app.get("/debug/observability/error", include_in_schema=True, tags=["debug"])
    def observability_error():
        """Raise an intentional 500 to verify observability in a local debug environment."""
        raise RuntimeError("Intentional observability demo error")


@app.on_event("startup")
def warm_up_menu_cache():
    """
    Cache Warm-Up: при старте приложения заполняем menu:all,
    чтобы первый запрос пользователя не шёл в БД.
    """
    try:
        from app.database import SessionLocal
        from app.modules.menu.repository import MenuRepository
        db = SessionLocal()
        try:
            repo = MenuRepository(db)
            repo.get_all()  # прогревает кеш (или использует уже существующий)
            print("[startup] Menu cache warmed up successfully")
        finally:
            db.close()
    except Exception as e:
        # Не падаем при старте, если БД/Redis ещё не готовы
        print(f"[startup] Menu cache warm-up skipped: {e}")