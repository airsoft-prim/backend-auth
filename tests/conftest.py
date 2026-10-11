"""Общие фикстуры тестов: приложение, клиент и подмены внешних ресурсов.

Redis подменяется хранилищем в памяти (`tests/doubles.py`), поэтому тесты не зависят
от внешнего сервера. Настоящий Redis проверяет только слой интеграционных тестов.
"""

from collections.abc import Iterator
from pathlib import Path

from fastapi import FastAPI
import pytest

from src.api.well_known.deps import get_jwk_publishing_service
from src.app import application
from src.providers.cache.repositories import PublicJWKRepository
from src.services.jwk import JWKGenerationService, JWKPublishingService
from tests.asgi_client import ASGIClient
from tests.doubles import InMemoryRedis, as_redis

__all__ = [
    "api_app",
    "api_client",
    "jwk_repository",
    "jwk_service",
    "jwks_client",
    "key_store_dir",
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
def jwk_service(key_store_dir: Path, jwk_repository: PublicJWKRepository) -> JWKGenerationService:
    """Отдаёт сервис генерации JWK поверх подмены Redis.

    Args:
        key_store_dir (Path): Каталог приватного ключа.
        jwk_repository (PublicJWKRepository): Репозиторий публичных ключей.

    Returns:
        JWKGenerationService: Сервис генерации ключей.
    """
    return JWKGenerationService(key_store_dir, jwk_repository)


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
