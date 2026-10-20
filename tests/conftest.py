"""Общие фикстуры тестов: приложение, клиент и подмены внешних ресурсов.

Redis подменяется хранилищем в памяти (`tests/doubles.py`), поэтому тесты не зависят
от внешнего сервера. Настоящий Redis проверяет только слой интеграционных тестов.
"""

from collections.abc import Iterator
from pathlib import Path

from fastapi import FastAPI
from pwdlib import PasswordHash
import pytest

from src.api.well_known.deps import get_jwk_publishing_service
from src.app import application
from src.general.security import PASSWORD_HASHER
from src.providers.cache.repositories import PublicJWKRepository
from src.providers.filesystem import FileSystem
from src.providers.filesystem.repositories import PrivateJWKRepository
from src.services.jwk import JWKGenerationService, JWKPublishingService
from src.services.jwt import JWTDecryptionService, JWTEncryptionService
from tests.asgi_client import ASGIClient
from tests.doubles import InMemoryRedis, as_redis

__all__ = [
    "api_app",
    "api_client",
    "decryption_service",
    "encryption_service",
    "file_system",
    "jwk_repository",
    "jwk_service",
    "jwks_client",
    "key_store_dir",
    "password_hash",
    "private_jwk_repository",
    "publishing_service",
    "redis_double",
    "unavailable_repository",
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

    Хешер берётся из общих средств безопасности (`src/general/security.py`), чтобы тест
    проверял именно ту конфигурацию Argon2id, с которой работает сервис.

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
def jwk_repository(redis_double: InMemoryRedis) -> PublicJWKRepository:
    """Отдаёт репозиторий публичных JWK поверх подмены Redis.

    Args:
        redis_double (InMemoryRedis): Подмена Redis.

    Returns:
        PublicJWKRepository: Репозиторий публичных ключей.
    """
    return PublicJWKRepository(as_redis(redis_double))


@pytest.fixture
def unavailable_repository() -> PublicJWKRepository:
    """Отдаёт репозиторий публичных JWK с недоступным Redis.

    Returns:
        PublicJWKRepository: Репозиторий, чьи обращения к кешу падают.
    """
    return PublicJWKRepository(as_redis(InMemoryRedis(unavailable=True)))


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
def private_jwk_repository(file_system: FileSystem) -> PrivateJWKRepository:
    """Отдаёт репозиторий приватного ключа поверх файловой системы.

    Args:
        file_system (FileSystem): Объект доступа к файловой системе.

    Returns:
        PrivateJWKRepository: Репозиторий приватного ключа подписи.
    """
    return PrivateJWKRepository(file_system)


@pytest.fixture
def jwk_service(
    private_jwk_repository: PrivateJWKRepository,
    jwk_repository: PublicJWKRepository,
) -> JWKGenerationService:
    """Отдаёт сервис генерации JWK поверх подмены Redis.

    Args:
        private_jwk_repository (PrivateJWKRepository): Репозиторий приватного ключа.
        jwk_repository (PublicJWKRepository): Репозиторий публичных ключей.

    Returns:
        JWKGenerationService: Сервис генерации ключей.
    """
    return JWKGenerationService(private_jwk_repository, jwk_repository)


@pytest.fixture
def publishing_service(jwk_repository: PublicJWKRepository) -> JWKPublishingService:
    """Отдаёт сервис публикации JWK поверх подмены Redis.

    Args:
        jwk_repository (PublicJWKRepository): Репозиторий публичных ключей.

    Returns:
        JWKPublishingService: Сервис публикации ключей.
    """
    return JWKPublishingService(jwk_repository=jwk_repository)


@pytest.fixture
def encryption_service(
    private_jwk_repository: PrivateJWKRepository,
) -> JWTEncryptionService:
    """Отдаёт сервис выпуска токенов поверх keyfile.

    Args:
        private_jwk_repository (PrivateJWKRepository): Репозиторий приватного ключа.

    Returns:
        JWTEncryptionService: Сервис подписи access-токенов.
    """
    return JWTEncryptionService(private_key_repository=private_jwk_repository)


@pytest.fixture
def decryption_service(jwk_repository: PublicJWKRepository) -> JWTDecryptionService:
    """Отдаёт сервис проверки токенов поверх подмены Redis.

    Args:
        jwk_repository (PublicJWKRepository): Репозиторий публичных ключей.

    Returns:
        JWTDecryptionService: Сервис проверки access-токенов.
    """
    return JWTDecryptionService(public_key_repository=jwk_repository)


@pytest.fixture
def jwks_client(api_app: FastAPI, jwk_repository: PublicJWKRepository) -> ASGIClient:
    """Отдаёт клиент эндпоинта JWKS с ключами из подмены Redis.

    Args:
        api_app (FastAPI): Приложение под тестом.
        jwk_repository (PublicJWKRepository): Репозиторий публичных ключей.

    Returns:
        ASGIClient: Клиент, чей сервис публикации читает подмену Redis.
    """
    api_app.dependency_overrides[get_jwk_publishing_service] = lambda: JWKPublishingService(
        jwk_repository=jwk_repository
    )

    return ASGIClient(api_app)
