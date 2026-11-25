from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.jwt import decode_token
from app.database import get_db
from app.models import User

# Схема извлечения токена из заголовка Authorization.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Извлекает текущего пользователя из JWT.
    Возбуждает HTTPException 401, если токен невалиден.
    """
    if credentials is None:
        raise HTTPException(
            401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials
    try:
        payload = decode_token(token)
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(401, "Invalid token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(401, "User not found")
    if user.is_blocked:
        raise HTTPException(403, "User is blocked")
    return user


def require_role(required_role: str):
    """
    Dependency для проверки роли пользователя.
    Возбуждает HTTPException 403, если роль не совпадает.
    """
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.name != required_role:
            raise HTTPException(403, "Access denied")
        return current_user
    return checker

