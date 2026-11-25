from app.models import MenuItem
from app.modules.menu.exceptions import MenuItemNameExistsError, MenuItemNotFoundError
from app.modules.menu.repository import MenuRepository


class MenuService:
    def __init__(self, repository: MenuRepository):
        self.repository = repository

    def get_all_items(self) -> list[MenuItem]:
        """Возвращает всё меню (данные приходят из кеша или БД — Service не знает откуда)."""
        return self.repository.get_all()

    def create_item(self, name: str, price: float) -> MenuItem:
        if price <= 0:
            raise ValueError("Цена должна быть положительной")

        if len(name) < 2:
            raise ValueError("Название блюда слишком короткое")

        if self.repository.get_by_name(name):
            raise MenuItemNameExistsError()

        new_item = self.repository.save(name=name, price=price)
        # Инвалидация кеша: меню изменилось
        self.repository.invalidate_cache()
        return new_item

    def update_item(self, item_id: int, name: str | None, price: float | None, is_available: bool | None) -> int:
        item = self.repository.get_by_id(item_id)
        if not item:
            raise MenuItemNotFoundError()

        if price is not None and price <= 0:
            raise ValueError("Цена должна быть положительной")

        if name is not None:
            item.name = name
        if price is not None:
            item.price = price
        if is_available is not None:
            item.is_available = is_available
        self.repository.update(item)
        # Инвалидация кеша: меню изменилось
        self.repository.invalidate_cache()
        return item_id
