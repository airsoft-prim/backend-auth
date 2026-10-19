from typing import Final

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool

from src.core.configs import Configs, config

MAX_ALIVE_CONNECTIONS: Final[int] = 30
POOL_SIZE: Final[int] = 10


def _create_engine(config: Configs) -> AsyncEngine:
    """Создание асинхронного движка SQLAlchemy.

    Args:
        config (Configs): Конфигурация проекта.

    Returns:
        Engine: Движок SQLAlchemy
    """
    return create_async_engine(
        config.database.DSN.encoded_string(),
        poolclass=AsyncAdaptedQueuePool,
        echo=config.app.DEBUG,
        pool_pre_ping=True,
        pool_size=POOL_SIZE,
        max_overflow=MAX_ALIVE_CONNECTIONS - POOL_SIZE,
    )


engine = _create_engine(config)
