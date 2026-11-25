class MenuItemNotFoundError(Exception):
    """Предмет из меню не найден."""
    pass


class MenuItemNameExistsError(Exception):
    """Такое имя предмета уже существует."""
    pass

