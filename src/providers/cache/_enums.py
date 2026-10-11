from enum import Enum

from src.core.configs import config


class StorageNumber(Enum):
    """Перечисление логических номеров БД Redis, используемых в приложении."""

    DEFAULT = config.cache.DB
    KEYS = 1
