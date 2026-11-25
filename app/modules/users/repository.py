"""
Инфраструктурный слой модуля пользователей.
Только работа с БД.
"""
from sqlalchemy.orm import Session

from app.models import Role, User


class UserRepository:
    """Инфраструктурный слой: только работа с БД."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_role_id(self, role: str) -> int:
        role_obj = self.db.query(Role).filter(Role.name == role).first()
        if not role_obj:
            raise ValueError(f"Роль '{role}' не найдена в БД")
        return role_obj.id

    def save(self, email: str, password_hash: str, phone: str | None) -> User:
        new_user = User(
            email=email,
            phone=phone,
            balance=0.0,
            is_blocked=False,
            password_hash=password_hash,
            role_id=self.get_role_id("student"),
        )
        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user)
        return new_user

    def update_balance(self, user: User, new_balance: float) -> None:
        user.balance = new_balance
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
