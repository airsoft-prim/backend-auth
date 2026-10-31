from collections.abc import Sequence
from typing import Protocol

from src.domain.entities import Session, User
from src.domain.enums import TokenType

# Публичный JWK в этом сервисе — набор строковых параметров (RFC 7517).
type JsonWebKey = dict[str, str]


class UserRepository(Protocol):
    """Порт доступа к учётным записям портала."""

    async def get(self, user_id: int) -> User | None: ...

    async def get_by_username(self, username: str) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def save(self, user: User) -> None: ...


class PasswordHasher(Protocol):
    """Порт хеширования и проверки паролей."""

    def hash(self, password: str) -> str: ...

    def verify(self, password: str, hashed: str, /) -> bool: ...


class PublicJwkRepository(Protocol):
    """Порт доступа к опубликованным публичным JWK."""

    async def store(self, kid: str, jwk: JsonWebKey) -> None: ...

    async def acquire(self, kid: str) -> JsonWebKey | None: ...

    async def acquire_all(self) -> Sequence[JsonWebKey]: ...

    async def expire_rotated(self, generated_kid: str, ttl: int) -> None: ...


class PrivateJwkRepository(Protocol):
    """Порт доступа к приватному ключу подписи."""

    async def acquire(self) -> bytes | None: ...

    async def store(self, payload: bytes) -> None: ...


class RevokedTokensRepository(Protocol):
    """Порт доступа к отозванным токенам и сессиям."""

    async def store(self, token_type: TokenType, token_id: str, ttl: int) -> None: ...

    async def check(self, token_type: TokenType, token_id: str) -> bool: ...

    async def store_session(self, sid: str, ttl: int) -> None: ...

    async def check_session(self, sid: str) -> bool: ...


class SessionRepository(Protocol):
    """Порт доступа к сессиям пользователей."""

    async def save(self, session: Session) -> None: ...

    async def get(self, sid: str) -> Session | None: ...

    async def list_active(self, user_id: int) -> Sequence[Session]: ...
