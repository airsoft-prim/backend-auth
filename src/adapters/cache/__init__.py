"""Подключения и хранилища `Redis`.

Создаёт клиенты и пулы для логических БД и объединяет репозитории ключей, маркеров отзыва и сессий.

Предоставляет `Redis`-адаптеры доменных портов для сборки прикладных сценариев.
"""

from ._enums import StorageNumber
from .client import create_client, get_bounded_client, get_client

__all__ = ["StorageNumber", "create_client", "get_bounded_client", "get_client"]
