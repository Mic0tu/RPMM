
import os

# Переменные окружения должны быть установлены ДО импорта приложения.
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://test:test@localhost:5432/test"
)
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

import pytest
from testcontainers.community.postgres import PostgresContainer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base


@pytest.fixture(scope="session")
def postgres():
    """Поднимает PostgreSQL в Docker на время тестов."""

    with PostgresContainer("postgres:15") as pg:
        database_url = pg.get_connection_url()

        # Передаём приложению URL тестовой PostgreSQL.
        os.environ["DATABASE_URL"] = database_url

        # Создаём таблицы.
        engine = create_engine(database_url)
        Base.metadata.create_all(bind=engine)
        engine.dispose()

        yield pg


@pytest.fixture
def db(postgres):
    """Создаёт отдельную сессию БД для теста."""

    engine = create_engine(postgres.get_connection_url())
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.fixture
def client(db):
    """Создаёт тестовый HTTP-клиент FastAPI."""

    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: db

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()
