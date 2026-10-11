from collections.abc import AsyncGenerator, Callable

from redis.asyncio import ConnectionPool, Redis

from src.core.configs import config

from ._enums import StorageNumber

_pools: dict[int, ConnectionPool] = {}


def _get_pool(db: int) -> ConnectionPool:
    """Возвращает пул соединений для указанной БД, создавая его при первом обращении.

    Пул живёт до завершения процесса приложения.

    Args:
        db (int): Номер логической БД Redis.

    Returns:
        ConnectionPool: Пул соединений, который выбирает эту БД при подключении.
    """
    if db not in _pools:
        _pools[db] = ConnectionPool(
            host=config.cache.HOST,
            port=config.cache.PORT,
            db=db,
            max_connections=config.cache.MAX_CONNECTIONS,
            decode_responses=True,
            retry_on_timeout=False,
            socket_connect_timeout=1,
        )

    return _pools[db]


def create_client(bounded_db: int | None = None) -> Redis:
    """Создаёт клиент Redis, привязанный к указанной БД.

    Клиент берёт соединение из пула этой БД и держит его до закрытия, поэтому передаётся
    потребителям с ограниченным временем жизни: на время запроса или работы фоновой задачи.

    Args:
        bounded_db (int | None, optional): Номер логической БД Redis. Если не передан,
            берётся БД из конфигурации (`CACHE_DB`). Defaults to None.

    Returns:
        Redis: Асинхронный клиент Redis.
    """
    db = StorageNumber.DEFAULT.value if bounded_db is None else bounded_db

    return Redis(
        connection_pool=_get_pool(db),
        single_connection_client=True,
        client_name=config.app.NAME,
    )


async def get_client() -> AsyncGenerator[Redis]:
    """Предоставляет асинхронный клиент Redis на время запроса.

    Соединение открывается и проверяется явно перед выдачей клиента, а пул
    соединений закрывается при завершении работы с клиентом (включая ошибки).

    Yields:
        AsyncGenerator[Redis]: Асинхронный клиент Redis.
    """
    async with create_client() as connected_client:
        yield connected_client


def get_bounded_client(to_db: int = 0) -> Callable[[], AsyncGenerator[Redis]]:
    """Создаёт фабрику зависимостей с клиентом Redis, привязанным к указанной БД.

    Возвращается именно фабрика: её подставляют как зависимость FastAPI, и каждый вызов
    фабрики отдаёт клиент в своём контексте. Нужна там, где обращение к БД по умолчанию
    (`CACHE_DB`) недопустимо, — например, для изолированной БД в тестах или для простой
    инкапсуляции данных внутри определённой БД.

    Args:
        to_db (int, optional): Номер логической БД Redis. Defaults to 0.

    Returns:
        Callable[[], AsyncGenerator[Redis]]: Фабрика асинхронных генераторов, отдающих
            клиент Redis, привязанный к БД `db`.
    """

    async def _get_client() -> AsyncGenerator[Redis]:
        """Отдаёт клиент Redis на время запроса.

        Yields:
            AsyncGenerator[Redis]: Клиент Redis, привязанный к БД `db`.
        """
        async with create_client(to_db) as connected_client:
            yield connected_client

    return _get_client
