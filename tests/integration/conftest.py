"""Фикстуры слоя integration: настоящий Redis.

Тесты слоя пропускаются явно, если Redis недоступен: без инфраструктуры проверять нечего,
и «зелёный» результат означал бы непроверенное поведение.
"""

from collections.abc import AsyncIterator

import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.core.configs import config
from src.providers.cache import StorageNumber, create_client

__all__ = ["redis_client"]


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
