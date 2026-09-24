from collections.abc import AsyncGenerator

from redis.asyncio import ConnectionPool, Redis

from src.core.configs import config

connection_pool = ConnectionPool(
    host=config.cache.HOST,
    port=config.cache.PORT,
    db=config.cache.DB,
    max_connections=config.cache.MAX_CONNECTIONS,
    decode_responses=True,
    retry_on_timeout=False,
    socket_connect_timeout=1,
)


async def get_client() -> AsyncGenerator[Redis]:
    """Предоставляет асинхронный клиент Redis на время запроса.

    Соединение открывается и проверяется явно перед выдачей клиента, а пул
    соединений закрывается при завершении работы с клиентом (включая ошибки).

    Yields:
        AsyncGenerator[Redis]: Асинхронный клиент Redis.
    """
    client = Redis(
        connection_pool=connection_pool,
        single_connection_client=True,
        client_name=config.app.NAME,
    )

    async with client as connected_client:
        yield connected_client
