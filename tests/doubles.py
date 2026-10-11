"""Тестовые двойники внешних ресурсов.

Redis заменяется подменой в памяти: проверяется отображение ключей и JSON в
репозитории, а не работа самого Redis. Настоящий сервер нужен только слою
интеграционных тестов.
"""

from collections.abc import AsyncIterator, Sequence
from fnmatch import fnmatch
from typing import Any, Self, cast

from redis.asyncio import Redis

__all__ = ["InMemoryRedis", "as_redis"]


class InMemoryPipeline:
    """Конвейер команд подмены Redis: копит TTL и применяет их по `execute`."""

    def __init__(self, storage: InMemoryRedis) -> None:
        """Инициализация конвейера.

        Args:
            storage (InMemoryRedis): Подмена Redis, в которую применяются команды.
        """
        self._storage = storage
        self._scheduled: list[tuple[str, int]] = []

    async def __aenter__(self) -> Self:
        """Входит в контекст конвейера.

        Returns:
            Self: Этот же конвейер.
        """
        return self

    async def __aexit__(self, *_: object) -> None:
        """Выходит из контекста конвейера, оставляя команды невыполненными."""

    def expire(self, key: str, ttl: int) -> None:
        """Откладывает назначение времени жизни ключа до `execute`.

        Args:
            key (str): Ключ Redis.
            ttl (int): Время жизни ключа в секундах.
        """
        self._scheduled.append((key, ttl))

    async def execute(self) -> list[bool]:
        """Применяет отложенные команды.

        Returns:
            list[bool]: Результат каждой команды, как у Redis.
        """
        for key, ttl in self._scheduled:
            self._storage.ttl[key] = ttl

        return [True] * len(self._scheduled)


class InMemoryRedis:
    """Подмена клиента Redis: значения и время жизни ключей в памяти.

    Повторяет только те вызовы, которые использует `PublicJWKRepository`:
    `set`, `get`, `mget`, `scan_iter` и `pipeline`.
    """

    def __init__(self, *, unavailable: bool = False) -> None:
        """Инициализация пустого хранилища.

        Args:
            unavailable (bool, optional): Признак недоступного Redis: любое обращение к
                хранилищу падает, как при отсутствии соединения. Defaults to False.
        """
        self.values: dict[str, str] = {}
        self.ttl: dict[str, int] = {}
        self._unavailable = unavailable

    async def set(self, key: str, value: str) -> None:
        """Сохраняет значение по ключу.

        Args:
            key (str): Ключ Redis.
            value (str): Значение ключа.
        """
        self._ensure_available()

        self.values[key] = value

    async def get(self, key: str) -> str | None:
        """Возвращает значение ключа.

        Args:
            key (str): Ключ Redis.

        Returns:
            str | None: Значение ключа или None, если ключа нет.
        """
        self._ensure_available()

        return self.values.get(key)

    async def mget(self, keys: Sequence[str]) -> list[str | None]:
        """Возвращает значения нескольких ключей.

        Args:
            keys (Sequence[str]): Ключи Redis.

        Returns:
            list[str | None]: Значения в порядке переданных ключей.
        """
        self._ensure_available()

        return [self.values.get(key) for key in keys]

    async def scan_iter(self, match: str | None = None) -> AsyncIterator[str]:
        """Перебирает ключи по glob-маске, как `scan_iter` Redis.

        Args:
            match (str | None, optional): Glob-маска ключей. Defaults to None.

        Yields:
            AsyncIterator[str]: Ключи, подходящие под маску.
        """
        self._ensure_available()

        pattern = "*" if match is None else match
        for key in list(self.values):
            if fnmatch(key, pattern):
                yield key

    def pipeline(self, **_options: Any) -> InMemoryPipeline:
        """Создаёт конвейер команд по образцу `Redis.pipeline`.

        Args:
            **_options (Any): Параметры клиента; подмена их не различает.

        Returns:
            InMemoryPipeline: Конвейер на этом хранилище.
        """
        return InMemoryPipeline(self)

    def _ensure_available(self) -> None:
        """Проверяет доступность хранилища.

        Raises:
            ConnectionError: Если подмена создана с признаком недоступного Redis.
        """
        if self._unavailable:
            msg = "Redis is unreachable."
            raise ConnectionError(msg)


def as_redis(double: InMemoryRedis) -> Redis:
    """Приводит подмену к типу клиента Redis.

    Подмена повторяет только вызовы, нужные репозиторию, но не наследует `Redis`:
    наследование потребовало бы совпадения подписей всего клиента.

    Args:
        double (InMemoryRedis): Подмена клиента.

    Returns:
        Redis: Тот же объект в типе клиента Redis.
    """
    return cast("Redis", double)
