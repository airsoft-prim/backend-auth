from collections.abc import Sequence
from typing import Protocol

from src.domain.entities import Session, User
from src.domain.enums import TokenType

# Публичный JWK в этом сервисе — набор строковых параметров (RFC 7517).
type JsonWebKey = dict[str, str]


class UserRepository(Protocol):
    """Порт доступа к учётным записям портала.

    Определяет поиск доменной сущности `User` по идентификатору, логину и адресу почты, а также её
    сохранение. Прикладные сценарии используют порт без зависимости от PostgreSQL.
    """

    async def get(self, user_id: int) -> User | None:
        """Возвращает учётную запись по идентификатору.

        Args:
            user_id (int): Идентификатор учётной записи.

        Returns:
            User | None: Учётная запись или `None`, если запись не найдена.
        """
        ...

    async def get_by_username(self, username: str) -> User | None:
        """Возвращает учётную запись по логину.

        Args:
            username (str): Логин учётной записи.

        Returns:
            User | None: Учётная запись или `None`, если логин не найден.
        """
        ...

    async def get_by_email(self, email: str) -> User | None:
        """Возвращает учётную запись по адресу почты.

        Args:
            email (str): Адрес электронной почты учётной записи.

        Returns:
            User | None: Учётная запись или `None`, если адрес не найден.
        """
        ...

    async def save(self, user: User) -> None:
        """Сохраняет учётную запись.

        Args:
            user (User): Доменная учётная запись.
        """
        ...


class PasswordHasher(Protocol):
    """Порт хеширования и проверки паролей.

    Определяет получение хеша и проверку открытого пароля по сохранённому хешу. Конкретный алгоритм
    задаётся адаптером.
    """

    def hash(self, password: str) -> str:
        """Хеширует пароль для хранения.

        Args:
            password (str): Пароль в открытом виде.

        Returns:
            str: Хеш переданного пароля.
        """
        ...

    def verify(self, password: str, hashed: str, /) -> bool:
        """Проверяет пароль по сохранённому хешу.

        Args:
            password (str): Пароль в открытом виде.
            hashed (str): Сохранённый хеш пароля.

        Returns:
            bool: `True`, если пароль соответствует хешу.
        """
        ...


class PublicJwkRepository(Protocol):
    """Порт доступа к опубликованным публичным JWK.

    Определяет публикацию и чтение публичных ключей по `kid`, получение набора JWKS и ограничение
    срока жизни ключей прошлых ротаций.
    """

    async def store(self, kid: str, jwk: JsonWebKey) -> None:
        """Публикует JWK по идентификатору ключа.

        Args:
            kid (str): Идентификатор публичного ключа.
            jwk (JsonWebKey): Параметры публичного ключа JWK.
        """
        ...

    async def acquire(self, kid: str) -> JsonWebKey | None:
        """Возвращает опубликованный JWK по идентификатору.

        Args:
            kid (str): Идентификатор публичного ключа.

        Returns:
            JsonWebKey | None: Публичный JWK или `None`, если ключ не опубликован.
        """
        ...

    async def acquire_all(self) -> Sequence[JsonWebKey]:
        """Возвращает все опубликованные публичные JWK.

        Returns:
            Sequence[JsonWebKey]: Опубликованные публичные ключи.
        """
        ...

    async def expire_rotated(self, generated_kid: str, ttl: int) -> None:
        """Назначает TTL ключам прошлых ротаций.

        Args:
            generated_kid (str): Идентификатор текущего ключа, исключённого из назначения TTL.
            ttl (int): Время жизни записи в секундах.
        """
        ...


class PrivateJwkRepository(Protocol):
    """Порт доступа к приватному ключу подписи.

    Передаёт приватный ключ как байты между файловым адаптером и сценариями подписи и ротации;
    отсутствие ключа представляется значением `None`.
    """

    async def acquire(self) -> bytes | None:
        """Читает приватный ключ подписи.

        Returns:
            bytes | None: Байты ключа или `None`, если ключ отсутствует.
        """
        ...

    async def store(self, payload: bytes) -> None:
        """Сохраняет байты приватного ключа подписи.

        Args:
            payload (bytes): Байты приватного ключа для сохранения.
        """
        ...


# TODO: перерабатывается — в сессионной модели инвалидация идёт через сессию, а не по
# отдельному токену; отзыв по `jti` пока остаётся только для ротации refresh-токена.
class RevokedTokensRepository(Protocol):
    """Порт доступа к отозванным токенам.

    Определяет хранение временного маркера отзыва по типу токена и `jti` и проверку наличия этого
    маркера.
    """

    async def store(self, token_type: TokenType, token_id: str, ttl: int) -> None:
        """Сохраняет маркер отзыва токена с TTL.

        Args:
            token_type (TokenType): Тип токена: `access` или `refresh`.
            token_id (str): Идентификатор токена из claim `jti`.
            ttl (int): Время жизни записи в секундах.
        """
        ...

    async def check(self, token_type: TokenType, token_id: str) -> bool:
        """Проверяет наличие маркера отзыва токена.

        Args:
            token_type (TokenType): Тип токена: `access` или `refresh`.
            token_id (str): Идентификатор токена из claim `jti`.

        Returns:
            bool: `True`, если токен помечен отозванным.
        """
        ...


class RevokedSessionsRepository(Protocol):
    """Порт доступа к отозванным сессиям.

    Определяет хранение временного маркера отзыва по `sid` и проверку отзыва всей сессии при
    авторизации.
    """

    async def store(self, sid: str, ttl: int) -> None:
        """Сохраняет маркер отзыва сессии с TTL.

        Args:
            sid (str): Идентификатор сессии.
            ttl (int): Время жизни записи в секундах.
        """
        ...

    async def check(self, sid: str) -> bool:
        """Проверяет наличие маркера отзыва сессии.

        Args:
            sid (str): Идентификатор сессии.

        Returns:
            bool: `True`, если сессия помечена отозванной.
        """
        ...


class SessionRepository(Protocol):
    """Порт доступа к сессиям пользователей.

    Определяет сохранение, получение по `sid` и выборку активных доменных сессий пользователя без
    привязки к `Redis`.
    """

    async def save(self, session: Session) -> None:
        """Сохраняет запись сессии.

        Args:
            session (Session): Доменная сессия для сохранения.
        """
        ...

    async def get(self, sid: str) -> Session | None:
        """Возвращает сессию по идентификатору.

        Args:
            sid (str): Идентификатор сессии.

        Returns:
            Session | None: Сессия или `None`, если доступной записи нет.
        """
        ...

    async def list_active(self, user_id: int) -> Sequence[Session]:
        """Возвращает активные сессии пользователя.

        Args:
            user_id (int): Идентификатор учётной записи.

        Returns:
            Sequence[Session]: Неотозванные сессии с неистёкшим сроком действия.
        """
        ...
