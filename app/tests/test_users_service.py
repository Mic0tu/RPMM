"""Unit-тесты UserService без БД."""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.users.exceptions import EmailAlreadyExistsError
from app.modules.users.service import UserService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo):
    return UserService(repository=mock_repo)


@patch("app.modules.users.service.hash_password", return_value="hashed")
def test_register_success(mock_hash, service, mock_repo):
    mock_repo.get_by_email.return_value = None
    saved = MagicMock()
    saved.id = 7
    saved.email = "a@b.ru"
    mock_repo.save.return_value = saved

    user = service.register_user("a@b.ru", "secret12", "+79001112233")

    assert user.id == 7
    mock_repo.save.assert_called_once()
    mock_hash.assert_called_once_with("secret12")


def test_register_email_exists(service, mock_repo):
    mock_repo.get_by_email.return_value = MagicMock()
    with pytest.raises(EmailAlreadyExistsError):
        service.register_user("a@b.ru", "secret12")


def test_register_short_password(service, mock_repo):
    mock_repo.get_by_email.return_value = None
    with pytest.raises(ValueError, match="Пароль"):
        service.register_user("a@b.ru", "123")


def test_top_up_success(service, mock_repo):
    user = MagicMock()
    user.balance = 100.0
    user.is_blocked = False
    mock_repo.get_by_id.return_value = user

    new_balance = service.top_up_balance(1, 50.0)

    assert new_balance == 150.0
    mock_repo.update_balance.assert_called_once_with(user, 150.0)


def test_top_up_blocked(service, mock_repo):
    user = MagicMock()
    user.is_blocked = True
    mock_repo.get_by_id.return_value = user
    with pytest.raises(ValueError, match="заблокирован"):
        service.top_up_balance(1, 10.0)
