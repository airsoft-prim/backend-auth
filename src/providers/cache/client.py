from collections.abc import AsyncGenerator

from redis.asyncio import Redis

from src.core.configs import config


async def get_client() -> AsyncGenerator[Redis]:
    """Предоставляет асинхронный клиент Redis на время запроса.

    Соединение открывается и проверяется явно перед выдачей клиента, а пул
    соединений закрывается при завершении работы с клиентом (включая ошибки).

    Yields:
        AsyncGenerator[Redis]: Асинхронный клиент Redis.
    """
    client = Redis.from_url(config.cache.DSN.encoded_string())

    try:
        await client.ping()
        yield client

    finally:
        await client.aclose()
