from enum import Enum

from src.config import config


class StorageNumber(Enum):
    """Перечисление логических номеров БД `Redis`, используемых в приложении.

    Разделяет данные по логическим БД: публичные ключи — `1`, отозванные токены и сессии — `2`,
    записи сессий — `3`. `DEFAULT` берётся из `CACHE_DB`.
    """

    DEFAULT = config.cache.DB
    KEYS = 1
    TOKENS = 2
    SESSIONS = 3
