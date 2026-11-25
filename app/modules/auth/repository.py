"""
Инфраструктурный слой модуля аутентификации.
Только работа с БД: пользователи и refresh-токены.
"""
import hashlib
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import RefreshToken, User


class AuthRepository:
    """Репозиторий для auth: поиск пользователя и сохранение refresh-токенов."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def save_refresh_token(self, user_id: int, token: str) -> None:
        """
        Сохраняет хеш refresh-токена (не сам токен) для возможности отзыва.
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        rt = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(days=7),
            is_revoked=False,
        )
        self.db.add(rt)
        self.db.commit()

    def get_refresh_token(self, token: str) -> RefreshToken | None:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return (
            self.db.query(RefreshToken)
            .filter(
                RefreshToken.token_hash == token_hash,
                RefreshToken.is_revoked == False,  # noqa: E712
            )
            .first()
        )

    def revoke_refresh_token(self, token: str) -> None:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        rt = (
            self.db.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash)
            .first()
        )
        if rt:
            rt.is_revoked = True
            self.db.add(rt)
            self.db.commit()

    def revoke_all_user_tokens(self, user_id: int) -> None:
        """Инвалидирует все refresh-токены пользователя (при компрометации)."""
        tokens = (
            self.db.query(RefreshToken)
            .filter(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False,  # noqa: E712
            )
            .all()
        )
        for t in tokens:
            t.is_revoked = True
            self.db.add(t)
        self.db.commit()
