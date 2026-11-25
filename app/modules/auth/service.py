"""
Слой бизнес-логики модуля аутентификации.
Не импортирует fastapi и sqlalchemy.
"""
from app.core.jwt import create_access_token, create_refresh_token
from app.core.security import verify_password
from app.modules.auth.repository import AuthRepository


class InvalidCredentialsError(Exception):
    """Неверный email или пароль."""
    pass


class AuthService:
    def __init__(self, repository: AuthRepository):
        self.repository = repository

    def login(self, email: str, password: str) -> dict:
        """Проверяет учётные данные и возвращает пару токенов."""
        user = self.repository.get_by_email(email)
        if not user or not user.password_hash:
            raise InvalidCredentialsError()
        if not verify_password(password, user.password_hash):
            raise InvalidCredentialsError()
        if user.is_blocked:
            raise InvalidCredentialsError()

        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)

        # Сохраняем refresh-токен в БД для возможности отзыва.
        self.repository.save_refresh_token(user.id, refresh_token)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }
