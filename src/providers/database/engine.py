from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool

from src.core.configs import Configs, config


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
        pool_size=10,
        max_overflow=20,
    )


engine = _create_engine(config)
