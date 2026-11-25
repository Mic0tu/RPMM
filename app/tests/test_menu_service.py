"""Unit-тесты MenuService без БД / Redis."""
from unittest.mock import MagicMock

import pytest

from app.modules.menu.exceptions import MenuItemNameExistsError, MenuItemNotFoundError
from app.modules.menu.service import MenuService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo):
    return MenuService(repository=mock_repo)


def test_create_item_success(service, mock_repo):
    mock_repo.get_by_name.return_value = None
    item = MagicMock()
    item.id = 3
    mock_repo.save.return_value = item

    result = service.create_item("Борщ", 150.0)

    assert result.id == 3
    mock_repo.invalidate_cache.assert_called_once()


def test_create_item_duplicate_name(service, mock_repo):
    mock_repo.get_by_name.return_value = MagicMock()
    with pytest.raises(MenuItemNameExistsError):
        service.create_item("Борщ", 150.0)


def test_create_item_bad_price(service, mock_repo):
    with pytest.raises(ValueError, match="Цена"):
        service.create_item("Суп", -1)


def test_update_item_success(service, mock_repo):
    item = MagicMock()
    mock_repo.get_by_id.return_value = item

    item_id = service.update_item(1, name="Новое", price=200.0, is_available=False)

    assert item_id == 1
    assert item.name == "Новое"
    assert item.price == 200.0
    assert item.is_available is False
    mock_repo.invalidate_cache.assert_called_once()


def test_update_item_not_found(service, mock_repo):
    mock_repo.get_by_id.return_value = None
    with pytest.raises(MenuItemNotFoundError):
        service.update_item(99, name="x", price=None, is_available=None)


def test_get_all_delegates_to_repo(service, mock_repo):
    mock_repo.get_all.return_value = [MagicMock()]
    assert len(service.get_all_items()) == 1
    mock_repo.get_all.assert_called_once()
