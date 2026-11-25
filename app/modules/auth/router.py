"""
Транспортный слой модуля аутентификации.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.rate_limit import rate_limit
from app.database import get_db
from app.modules.auth.repository import AuthRepository
from app.modules.auth.service import AuthService, InvalidCredentialsError

router = APIRouter()


class LoginSchema(BaseModel):
    """Схема запроса на вход."""
    email: EmailStr
    password: str


class RefreshSchema(BaseModel):
    """Схема запроса на обновление токена."""
    refresh_token: str


@router.post("/auth/login", dependencies=[Depends(rate_limit(5, 60))])
def login(payload: LoginSchema, db: Session = Depends(get_db)):
    """Аутентификация пользователя и выдача пары токенов."""
    repository = AuthRepository(db)
    service = AuthService(repository)
    try:
        return service.login(payload.email, payload.password)
    except InvalidCredentialsError:
        raise HTTPException(status_code=401, detail="Invalid email or password")
