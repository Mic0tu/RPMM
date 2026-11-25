import os
import pytest
from testcontainers.postgres import PostgresContainer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base

@pytest.fixture(scope="session")
def postgres():
    """Поднимает пустую PostgreSQL в Docker на время тестов."""
    with PostgresContainer("postgres:15") as pg:
        # Подменяем URL для приложения
        os.environ["DATABASE_URL"] = pg.get_connection_url()
        # Отключаем OTel, чтобы он не спамил при тестах
        os.environ["OTEL_SDK_DISABLED"] = "true" 
        
        # Создаем таблицы напрямую из моделей (вместо Alembic)
        engine = create_engine(pg.get_connection_url())
        Base.metadata.create_all(bind=engine)
        
        yield pg

@pytest.fixture
def db(postgres):
    engine = create_engine(postgres.get_connection_url())
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()

@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db
    
    app.dependency_overrides[get_db] = lambda: db
    
    # ВАЖНО: мы НЕ используем 'with TestClient(app)', 
    # чтобы не запускать событие startup (прогрев Redis), которое вешает тест
    client = TestClient(app)
    yield client
    
    app.dependency_overrides.clear()