"""Фикстуры слоя integration: настоящие Redis и PostgreSQL.

Тесты слоя пропускаются явно, если инфраструктура недоступна: без неё проверять нечего,
и «зелёный» результат означал бы непроверенное поведение.
"""

from collections.abc import AsyncIterator

import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.configs import config
from src.providers.cache import StorageNumber, create_client
from src.providers.database import BaseModel, engine

__all__ = ["database_session", "redis_client"]


@pytest.fixture
async def redis_client() -> AsyncIterator[Redis]:
    """Отдаёт клиент Redis из БД публичных ключей.

    Yields:
        AsyncIterator[Redis]: Клиент Redis, привязанный к БД публичных ключей. Если Redis
            недоступен по адресу из конфигурации, тест слоя пропускается с причиной.
    """
    client = create_client(StorageNumber.KEYS.value)

    try:
        await client.ping()
    except (RedisError, OSError) as error:
        await client.aclose()
        pytest.skip(f"Redis is not available at {config.cache.HOST}:{config.cache.PORT}: {error}")

    yield client
    await client.aclose()


@pytest.fixture
async def database_session() -> AsyncIterator[AsyncSession]:
    """Отдаёт сессию БД с таблицами схемы `auth`.

    Миграций с таблицами ещё нет, поэтому схема и таблицы создаются из метаданных
    моделей. DDL в PostgreSQL транзакционен, поэтому тест идёт в транзакции, которая
    откатывается в конце: и таблицы, и записи исчезают, и БД возвращается в исходное
    состояние. Если PostgreSQL недоступен по адресу из конфигурации, тест слоя
    пропускается с причиной.

    Yields:
        AsyncIterator[AsyncSession]: Сессия БД, привязанная к транзакции теста.
    """
    try:
        connection = await engine.connect()
    except (SQLAlchemyError, OSError) as error:
        pytest.skip(
            f"PostgreSQL is not available at {config.database.HOST}:{config.database.PORT}: {error}"
        )

    try:
        transaction = await connection.begin()

        await connection.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
        await connection.run_sync(BaseModel.metadata.create_all)

        # Коммит внутри репозитория снимает точку сохранения, а не транзакцию теста:
        # откат в конце возвращает БД в исходное состояние.
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()

    finally:
        await connection.close()
