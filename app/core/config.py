from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения, загружаемые из .env."""
    SECRET_KEY: str
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379"
    DEBUG: bool = False
    ALLOWED_ORIGINS: list[str] = []
    RABBITMQ_URL: str = "amqp://sirius:sirius@localhost:5672/"
    SENTRY_DSN: str | None = None
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4318/v1/traces"
    GRPC_DELIVERY_HOST: str = "localhost"
    GRPC_DELIVERY_PORT: int = 50051

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
