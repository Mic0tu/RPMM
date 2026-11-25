"""
Слой бизнес-логики модуля пользователей.
Не импортирует fastapi и sqlalchemy.
"""
from app.core.security import hash_password
from app.models import User
from app.modules.users.exceptions import EmailAlreadyExistsError
from app.modules.users.repository import UserRepository


class UserService:
    """Слой бизнес-логики. Не импортирует fastapi и sqlalchemy."""

    def __init__(self, repository: UserRepository):
        self.repository = repository

    def register_user(self, email: str, password: str, phone: str | None = None) -> User:
        # Бизнес-правило: email должен быть уникальным
        existing = self.repository.get_by_email(email)
        if existing:
            raise EmailAlreadyExistsError()

        # Бизнес/техническая проверка телефона
        if phone and len(phone) < 10:
            raise ValueError("Некорректный формат номера телефона")

        if not password or len(password) < 6:
            raise ValueError("Пароль должен содержать не менее 6 символов")

        new_user = self.repository.save(
            email=email,
            phone=phone,
            password_hash=hash_password(password),
        )
        return new_user

    def top_up_balance(self, user_id: int, amount: float) -> float:
        if amount <= 0:
            raise ValueError("Сумма пополнения должна быть положительной")

        user = self.repository.get_by_id(user_id)
        if not user:
            raise ValueError("Пользователь не найден")

        if user.is_blocked:
            raise ValueError("Пользователь заблокирован. Пополнение невозможно")

        if amount > 50000:
            raise ValueError("Максимальная сумма пополнения — 50000 рублей")

        new_balance = user.balance + amount
        self.repository.update_balance(user, new_balance)

        return new_balance
