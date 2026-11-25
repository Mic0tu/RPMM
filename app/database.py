"""
Модуль инициализации подключения к СУБД PostgreSQL.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

try:
    from app.core.config import settings
    DATABASE_URL = settings.DATABASE_URL
except Exception:
    import os
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://sirius:sirius@localhost:5432/sirius_food",
    )

# psycopg2 driver prefix for SQLAlchemy 2.x
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Генератор сессии базы данных для использования в Depends."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
