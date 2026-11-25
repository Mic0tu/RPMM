"""Доменные исключения модуля доставки."""


class OrderNotFoundError(Exception):
    """Заказ не найден."""
    pass


class CourierNotFoundError(Exception):
    """Курьер не найден."""
    pass


class DeliveryNotFoundError(Exception):
    """Доставка не найдена."""
    pass


class AccessDeniedError(Exception):
    """Нет прав на операцию."""
    pass


class BusinessRuleError(Exception):
    """Нарушение бизнес-правила."""
    pass
