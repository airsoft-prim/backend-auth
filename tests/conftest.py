"""Общие фикстуры тестов: приложение, клиент и подмены внешних ресурсов.

Redis подменяется хранилищем в памяти (`tests/doubles.py`), поэтому тесты не зависят
от внешнего сервера. Настоящий Redis проверяет только слой интеграционных тестов.
"""

from collections.abc import Iterator
from pathlib import Path

from fastapi import FastAPI
from pwdlib import PasswordHash
import pytest

from src.adapters.cache.repositories import (
    RedisPublicJwkRepository,
    RedisRevokedTokensRepository,
    RedisSessionRepository,
)
from src.adapters.crypto.hasher import PASSWORD_HASHER
from src.adapters.filesystem import FileSystem
from src.adapters.filesystem.repositories import FilePrivateJwkRepository
from src.app import application
from src.application.jwk import CollectJwks, RotateJwk
from src.application.token import SignToken, VerifyToken
from src.config import config
from src.domain.tokens import (
    AccessTokenClaims,
    AccessTokenConfig,
    RefreshTokenClaims,
    RefreshTokenConfig,
)
from src.interface.well_known.deps import get_collect_jwks
from tests.asgi_client import ASGIClient
from tests.doubles import InMemoryRedis, as_redis

__all__ = [
    "api_app",
    "api_client",
    "blacklisted_tokens_repository",
    "collect_jwks",
    "file_system",
    "jwk_repository",
    "jwks_client",
    "key_store_dir",
    "password_hash",
    "private_jwk_repository",
    "redis_double",
    "rotate_jwk",
    "session_repository",
    "sign_refresh_token",
    "sign_token",
    "unavailable_repository",
    "verify_refresh_token",
    "verify_token",
]


@pytest.fixture
def api_app() -> Iterator[FastAPI]:
    """Отдаёт приложение и снимает подмены зависимостей после теста.

    Yields:
        Iterator[FastAPI]: Приложение под тестом.
    """
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
def api_client(api_app: FastAPI) -> ASGIClient:
    """Отдаёт клиент приложения с настоящими зависимостями.

    Args:
        api_app (FastAPI): Приложение под тестом.

    Returns:
        ASGIClient: Клиент HTTP-контракта.
    """
    return ASGIClient(api_app)


@pytest.fixture
def password_hash() -> PasswordHash:
    """Отдаёт хешер паролей, тот же, что собирается для приложения.

    Хешер берётся из общих средств безопасности, чтобы тест проверял именно ту
    конфигурацию Argon2id, с которой работает сервис.

    Returns:
        PasswordHash: Хешер паролей.
    """
    return PASSWORD_HASHER


@pytest.fixture
def redis_double() -> InMemoryRedis:
    """Отдаёт пустую подмену Redis.

    Returns:
        InMemoryRedis: Хранилище в памяти.
    """
    return InMemoryRedis()


@pytest.fixture
def jwk_repository(redis_double: InMemoryRedis) -> RedisPublicJwkRepository:
    """Отдаёт репозиторий публичных JWK поверх подмены Redis.

    Args:
        redis_double (InMemoryRedis): Подмена Redis.

    Returns:
        RedisPublicJwkRepository: Репозиторий публичных ключей.
    """
    return RedisPublicJwkRepository(as_redis(redis_double))


@pytest.fixture
def blacklisted_tokens_repository(redis_double: InMemoryRedis) -> RedisRevokedTokensRepository:
    """Отдаёт репозиторий отозванных токенов поверх подмены Redis.

    Args:
        redis_double (InMemoryRedis): Подмена Redis.

    Returns:
        RedisRevokedTokensRepository: Репозиторий отозванных токенов.
    """
    return RedisRevokedTokensRepository(as_redis(redis_double))


@pytest.fixture
def session_repository(redis_double: InMemoryRedis) -> RedisSessionRepository:
    """Отдаёт репозиторий сессий поверх подмены Redis.

    Args:
        redis_double (InMemoryRedis): Подмена Redis.

    Returns:
        RedisSessionRepository: Репозиторий сессий пользователей.
    """
    return RedisSessionRepository(as_redis(redis_double))


@pytest.fixture
def unavailable_repository() -> RedisPublicJwkRepository:
    """Отдаёт репозиторий публичных JWK с недоступным Redis.

    Returns:
        RedisPublicJwkRepository: Репозиторий, чьи обращения к кешу падают.
    """
    return RedisPublicJwkRepository(as_redis(InMemoryRedis(unavailable=True)))


@pytest.fixture
def key_store_dir(tmp_path: Path) -> Path:
    """Отдаёт каталог для приватного ключа подписи.

    Args:
        tmp_path (Path): Временный каталог теста.

    Returns:
        Path: Путь к каталогу ключа.
    """
    return tmp_path / "keys"


@pytest.fixture
def file_system(key_store_dir: Path) -> FileSystem:
    """Отдаёт объект файловой системы в каталоге ключа подписи.

    Args:
        key_store_dir (Path): Каталог ключа подписи; создаётся при первой записи.

    Returns:
        FileSystem: Объект доступа к файловой системе.
    """
    return FileSystem(key_store_dir)


@pytest.fixture
def private_jwk_repository(file_system: FileSystem) -> FilePrivateJwkRepository:
    """Отдаёт репозиторий приватного ключа поверх файловой системы.

    Args:
        file_system (FileSystem): Объект доступа к файловой системе.

    Returns:
        FilePrivateJwkRepository: Репозиторий приватного ключа подписи.
    """
    return FilePrivateJwkRepository(file_system)


@pytest.fixture
def rotate_jwk(
    private_jwk_repository: FilePrivateJwkRepository,
    jwk_repository: RedisPublicJwkRepository,
) -> RotateJwk:
    """Отдаёт use case ротации JWK поверх подмены Redis.

    Args:
        private_jwk_repository (FilePrivateJwkRepository): Репозиторий приватного ключа.
        jwk_repository (RedisPublicJwkRepository): Репозиторий публичных ключей.

    Returns:
        RotateJwk: Use case генерации и ротации ключей.
    """
    return RotateJwk(private_jwk_repository, jwk_repository)


@pytest.fixture
def collect_jwks(jwk_repository: RedisPublicJwkRepository) -> CollectJwks:
    """Отдаёт use case сбора JWK поверх подмены Redis.

    Args:
        jwk_repository (RedisPublicJwkRepository): Репозиторий публичных ключей.

    Returns:
        CollectJwks: Use case сбора публичных ключей.
    """
    return CollectJwks(jwks=jwk_repository)


@pytest.fixture
def sign_token(
    private_jwk_repository: FilePrivateJwkRepository,
) -> SignToken:
    """Отдаёт use case выпуска токенов поверх keyfile.

    Args:
        private_jwk_repository (FilePrivateJwkRepository): Репозиторий приватного ключа.

    Returns:
        SignToken: Use case подписи access-токенов.
    """
    token_config = AccessTokenConfig(
        issuer=config.app.NAME,
        audience=config.app.PROJECT,
        ttl=config.security.ACCESS_TOKEN_TTL,
    )

    return SignToken(token_config, private_jwk_repository)


@pytest.fixture
def verify_token(jwk_repository: RedisPublicJwkRepository) -> VerifyToken[AccessTokenClaims]:
    """Отдаёт use case проверки токенов поверх подмены Redis.

    Args:
        jwk_repository (RedisPublicJwkRepository): Репозиторий публичных ключей.

    Returns:
        VerifyToken[AccessTokenClaims]: Use case проверки access-токенов.
    """
    token_config = AccessTokenConfig(
        issuer=config.app.NAME,
        audience=config.app.PROJECT,
        ttl=config.security.ACCESS_TOKEN_TTL,
    )

    return VerifyToken(token_config, jwk_repository)


@pytest.fixture
def sign_refresh_token(
    private_jwk_repository: FilePrivateJwkRepository,
) -> SignToken:
    """Отдаёт use case выпуска refresh-токенов поверх keyfile.

    Args:
        private_jwk_repository (FilePrivateJwkRepository): Репозиторий приватного ключа.

    Returns:
        SignToken: Use case подписи refresh-токенов.
    """
    token_config = RefreshTokenConfig(
        issuer=config.app.NAME,
        audience=config.app.NAME,
        ttl=config.security.REFRESH_TOKEN_TTL,
    )

    return SignToken(token_config, private_jwk_repository)


@pytest.fixture
def verify_refresh_token(
    jwk_repository: RedisPublicJwkRepository,
) -> VerifyToken[RefreshTokenClaims]:
    """Отдаёт use case проверки refresh-токенов поверх подмены Redis.

    Args:
        jwk_repository (RedisPublicJwkRepository): Репозиторий публичных ключей.

    Returns:
        VerifyToken[RefreshTokenClaims]: Use case проверки refresh-токенов.
    """
    token_config = RefreshTokenConfig(
        issuer=config.app.NAME,
        audience=config.app.NAME,
        ttl=config.security.REFRESH_TOKEN_TTL,
    )

    return VerifyToken(token_config, jwk_repository)


@pytest.fixture
def jwks_client(api_app: FastAPI, jwk_repository: RedisPublicJwkRepository) -> ASGIClient:
    """Отдаёт клиент эндпоинта JWKS с ключами из подмены Redis.

    Args:
        api_app (FastAPI): Приложение под тестом.
        jwk_repository (RedisPublicJwkRepository): Репозиторий публичных ключей.

    Returns:
        ASGIClient: Клиент, чей сервис публикации читает подмену Redis.
    """
    api_app.dependency_overrides[get_collect_jwks] = lambda: CollectJwks(jwks=jwk_repository)

    return ASGIClient(api_app)
