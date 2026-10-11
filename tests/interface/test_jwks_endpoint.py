"""Тесты HTTP-контракта публикации публичных ключей подписи."""

from fastapi import status
import pytest

from src.providers.cache.repositories import PublicJWKRepository
from src.services.jwk import JWKGenerationService
from tests.asgi_client import ASGIClient
from tests.interface.conftest import JWKSClientFactory

JWKS_PATH = "/.well-known/jwks.json"
KEY_TTL_SECONDS = 3600


async def test_get_jwks_returns_published_key(
    jwks_client: ASGIClient,
    jwk_service: JWKGenerationService,
) -> None:
    """Набор публичных ключей подписи.

    Given: сервис сгенерировал и опубликовал ключ подписи,
    When: потребитель запрашивает JWKS,
    Then: приходит 200 с опубликованным ключом и без приватной части.
    """
    # Дано
    published = await jwk_service.generate_jwk(KEY_TTL_SECONDS)

    # Когда
    response = await jwks_client.get(JWKS_PATH)

    # Тогда
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "application/json"

    keys = response.payload["keys"]
    assert len(keys) == 1

    key = keys[0]
    assert key["kid"] == published.key_id
    assert key["kty"] == "OKP"
    assert key["crv"] == "Ed25519"
    assert key["alg"] == "EdDSA"
    assert key["use"] == "sig"
    assert "d" not in key


async def test_get_jwks_returns_empty_set_when_nothing_is_published(
    jwks_client: ASGIClient,
) -> None:
    """Пустой набор ключей.

    Given: ни один ключ подписи ещё не сгенерирован,
    When: потребитель запрашивает JWKS,
    Then: приходит 200 с пустым набором — это корректный ответ, а не ошибка.
    """
    # Когда
    response = await jwks_client.get(JWKS_PATH)

    # Тогда
    assert response.status_code == status.HTTP_200_OK
    assert response.payload == {"keys": []}


@pytest.mark.parametrize("method", ["POST", "HEAD"])
async def test_jwks_denies_methods_other_than_get(
    jwks_client: ASGIClient,
    method: str,
) -> None:
    """Методы, отличные от GET.

    Given: маршрут отдаёт набор ключей только методом GET,
    When: запрос приходит другим методом,
    Then: приходит 405 с указанием разрешённого метода.
    """
    # Когда
    response = await jwks_client.request(method, JWKS_PATH)

    # Тогда
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert "GET" in response.headers["allow"]


async def test_get_jwks_fails_with_server_error_when_cache_is_unavailable(
    jwks_client_factory: JWKSClientFactory,
    unavailable_repository: PublicJWKRepository,
) -> None:
    """Отказ кеша публичных ключей.

    Given: Redis с публичными JWK недоступен,
    When: потребитель запрашивает JWKS,
    Then: приходит 500: набор ключей нечем собрать.
    """
    # Дано
    client = jwks_client_factory(unavailable_repository)

    # Когда
    response = await client.get(JWKS_PATH)

    # Тогда
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
