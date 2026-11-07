"""Тестовые двойники внешних ресурсов.

Redis заменяется подменой в памяти: проверяется отображение ключей и JSON в
репозитории, а не работа самого Redis. Учётные записи портала в unit-тестах живут в
подмене репозитория — так сервисный слой проверяется без PostgreSQL. Настоящие серверы
нужны только слою интеграционных тестов.
"""

from collections.abc import AsyncIterator, Sequence
from fnmatch import fnmatch
from typing import Any, Self, cast

from redis.asyncio import Redis

from src.domain.entities import User
from src.domain.ports import UserRepository

type StringSet = set[str]


class InMemoryPipeline:
    """Конвейер команд подмены Redis: копит TTL и применяет их по `execute`."""

    def __init__(self, storage: InMemoryRedis) -> None:
        """Инициализация конвейера.

        Args:
            storage (InMemoryRedis): Подмена Redis, в которую применяются команды.
        """
        self._storage = storage
        self._scheduled: list[tuple[str, int, bool]] = []

    async def __aenter__(self) -> Self:
        """Входит в контекст конвейера.

        Returns:
            Self: Этот же конвейер.
        """
        return self

    async def __aexit__(self, *_: object) -> None:
        """Выходит из контекста конвейера, оставляя команды невыполненными."""

    def expire(self, key: str, ttl: int, *, nx: bool = False) -> None:
        """Откладывает назначение времени жизни ключа до `execute`.

        Args:
            key (str): Ключ Redis.
            ttl (int): Время жизни ключа в секундах.
            nx (bool, optional): Назначать срок только ключу без TTL, как `EXPIRE ... NX`.
                Defaults to False.
        """
        self._scheduled.append((key, ttl, nx))

    async def execute(self) -> list[bool]:
        """Применяет отложенные команды.

        Returns:
            list[bool]: Результат каждой команды, как у Redis.
        """
        applied: list[bool] = []

        for key, ttl, nx in self._scheduled:
            if nx and key in self._storage.ttl:
                applied.append(False)
                continue

            self._storage.ttl[key] = ttl
            applied.append(True)

        return applied


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
        self.sets: dict[str, set[str]] = {}
        self._unavailable = unavailable

    async def set(self, key: str, value: str, *, ex: int | None = None) -> None:
        """Сохраняет значение по ключу.

        Args:
            key (str): Ключ Redis.
            value (str): Значение ключа.
            ex (int | None, optional): Время жизни ключа в секундах, как `EX` у Redis.
                Defaults to None.
        """
        self._ensure_available()

        self.values[key] = value

        if ex is not None:
            self.ttl[key] = ex

    async def get(self, key: str) -> str | None:
        """Возвращает значение ключа.

        Args:
            key (str): Ключ Redis.

        Returns:
            str | None: Значение ключа или None, если ключа нет.
        """
        self._ensure_available()

        return self.values.get(key)

    async def exists(self, key: str) -> int:
        """Сообщает, есть ли значение по ключу.

        Args:
            key (str): Ключ Redis.

        Returns:
            int: 1, если ключ есть, иначе 0, как у Redis.
        """
        self._ensure_available()

        return int(key in self.values)

    async def sadd(self, key: str, value: str) -> int:
        """Добавляет значение в множество, как `SADD` у Redis.

        Args:
            key (str): Ключ множества.
            value (str): Добавляемое значение.

        Returns:
            int: 1, если значение добавлено, иначе 0, как у Redis.
        """
        self._ensure_available()

        members = self.sets.setdefault(key, set())

        if value in members:
            return 0

        members.add(value)

        return 1

    async def smembers(self, key: str) -> StringSet:
        """Возвращает множество по ключу, как `SMEMBERS` у Redis.

        Args:
            key (str): Ключ множества.

        Returns:
            set[str]: Члены множества.
        """
        self._ensure_available()

        return self.sets.get(key, set())

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


class InMemoryUserRepository:
    """Подмена репозитория учётных записей: учётные записи в памяти.

    Повторяет только те вызовы, которые нужны сервису учётных записей: поиск по логину
    и по адресу и сохранение записи. Адрес сравнивается без учёта регистра — как
    функциональный индекс `lower(email)` в БД. Значения, которые проставляет сама БД
    (идентификатор, роль, метки времени), подмена не подставляет.
    """

    def __init__(self) -> None:
        """Инициализация пустого хранилища."""
        self.users: list[User] = []

    async def get(self, user_id: int) -> User | None:
        """Возвращает учётную запись по идентификатору.

        Args:
            user_id (int): Идентификатор учётной записи.

        Returns:
            User | None: Учётная запись или None, если её нет.
        """
        return next((user for user in self.users if user.id == user_id), None)

    async def get_by_username(self, username: str) -> User | None:
        """Возвращает учётную запись по логину.

        Args:
            username (str): Логин учётной записи.

        Returns:
            User | None: Учётная запись или None, если логин ещё свободен.
        """
        return next((user for user in self.users if user.username == username), None)

    async def get_by_email(self, email: str) -> User | None:
        """Возвращает учётную запись по адресу без учёта регистра.

        Args:
            email (str): Адрес электронной почты учётной записи.

        Returns:
            User | None: Учётная запись или None, если адрес ещё свободен.
        """
        lowered_email = email.lower()

        return next((user for user in self.users if user.email.lower() == lowered_email), None)

    async def save(self, entity: User) -> None:
        """Сохраняет учётную запись в хранилище.

        Args:
            entity (User): Учётная запись для сохранения.
        """
        self.users.append(entity)


def as_user_repository(double: InMemoryUserRepository) -> UserRepository:
    """Приводит подмену к типу репозитория учётных записей.

    Подмена повторяет только вызовы, нужные сервису, но не наследует репозиторий:
    наследование потребовало бы настоящей сессии БД.

    Args:
        double (InMemoryUserRepository): Подмена репозитория.

    Returns:
        UserRepository: Та же подмена в типе репозитория учётных записей.
    """
    return cast("UserRepository", double)
