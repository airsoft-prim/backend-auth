from enum import Enum

from src.config import config


class StorageNumber(Enum):
    """Перечисление логических номеров БД Redis, используемых в приложении."""

    DEFAULT = config.cache.DB
    KEYS = 1
    TOKENS = 2
    SESSIONS = 3
