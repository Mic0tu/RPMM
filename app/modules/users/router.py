"""
Модуль управления пользователями.
Транспортный слой (API Layer).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.database import get_db
from app.models import User
from app.modules.users.exceptions import EmailAlreadyExistsError
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserService
from app.schemas import UserCreate

router = APIRouter()


@router.post("/register")
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    repository = UserRepository(db)
    service = UserService(repository)

    try:
        new_user = service.register_user(
            email=payload.email,
            password=payload.password,
            phone=payload.phone,
        )
    except EmailAlreadyExistsError:
        raise HTTPException(status_code=400, detail="Email already exists")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "status": "success",
        "user_id": new_user.id,
        "email": new_user.email,
    }


@router.post("/{user_id}/topup")
def top_up_balance(
    user_id: int,
    amount: float,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    repository = UserRepository(db)
    service = UserService(repository)

    try:
        new_balance = service.top_up_balance(user_id=user_id, amount=amount)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "success", "new_balance": new_balance}
