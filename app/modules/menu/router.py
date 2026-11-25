"""
Модуль управления меню столовой.
Транспортный слой (API Layer).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MenuItem, User
from app.schemas import MenuItemCreate, MenuItemUpdate
from app.core.dependencies import get_current_user, require_role
from app.modules.menu.exceptions import MenuItemNotFoundError, MenuItemNameExistsError
from app.modules.menu.repository import MenuRepository
from app.modules.menu.service import MenuService

router = APIRouter()


@router.get("/items")
def get_menu_items(db: Session = Depends(get_db)):
    """
    Получить всё меню.
    Эндпоинт публичный (без авторизации) для удобства нагрузочного тестирования Locust.
    Данные отдаются из Redis-кеша (Cache-Aside) или из PostgreSQL при miss.
    """
    repository = MenuRepository(db)
    service = MenuService(repository)
    items = service.get_all_items()
    return [
        {
            "id": item.id,
            "name": item.name,
            "price": item.price,
            "is_available": item.is_available,
        }
        for item in items
    ]


@router.get("/items/{item_id}")
def get_menu_item(item_id: int, db: Session = Depends(get_db)):
    """Get one public menu item for the SSR storefront."""
    item = MenuRepository(db).get_by_id(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Menu item not found")
    return {
        "id": item.id,
        "name": item.name,
        "price": item.price,
        "is_available": item.is_available,
    }


@router.post("/items")
def create_menu_item(
    payload: MenuItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("cook")),
):
    repository = MenuRepository(db)
    service = MenuService(repository)

    try:
        new_item = service.create_item(name=payload.name, price=payload.price)
    except MenuItemNameExistsError:
        raise HTTPException(400, "Menu Item name already exists")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "success", "item_id": new_item.id}


@router.patch("/items/{item_id}")
def update_menu_item(
    item_id: int,
    payload: MenuItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("cook")),
):
    repository = MenuRepository(db)
    service = MenuService(repository)

    try:
        item_id = service.update_item(
            item_id=item_id,
            name=payload.name,
            price=payload.price,
            is_available=payload.is_available,
        )
    except MenuItemNotFoundError:
        raise HTTPException(404, "Menu Item not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "success", "item_id": item_id}
