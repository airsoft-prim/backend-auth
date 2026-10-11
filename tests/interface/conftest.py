"""Фикстуры слоя interface: клиент эндпоинта JWKS."""

from collections.abc import Callable

from fastapi import FastAPI
import pytest

from src.api.well_known.deps import get_jwk_publishing_service
from src.providers.cache.repositories import PublicJWKRepository
from src.services.jwk import JWKPublishingService
from tests.asgi_client import ASGIClient

__all__ = ["JWKSClientFactory", "jwks_client_factory"]

type JWKSClientFactory = Callable[[PublicJWKRepository], ASGIClient]


@pytest.fixture
def jwks_client_factory(api_app: FastAPI) -> JWKSClientFactory:
    """Собирает клиент JWKS с указанным репозиторием публичных ключей.

    Подменяется только репозиторий: маршрутизация, схемы ответа и обработка ошибок
    остаются настоящими.

    Args:
        api_app (FastAPI): Приложение под тестом.

    Returns:
        JWKSClientFactory: Фабрика клиентов эндпоинта.
    """

    def _factory(repository: PublicJWKRepository) -> ASGIClient:
        api_app.dependency_overrides[get_jwk_publishing_service] = lambda: JWKPublishingService(
            jwk_repository=repository
        )

        return ASGIClient(api_app)

    return _factory
