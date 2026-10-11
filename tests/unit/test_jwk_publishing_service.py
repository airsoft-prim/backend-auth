"""Тесты публикации публичных JWK."""

import pytest

from src.general.exceptions import RepositoryError
from src.providers.cache.repositories import PublicJWKRepository
from src.services.jwk import JWKGenerationService, JWKPublishingService

KEY_TTL_SECONDS = 3600


async def test_collect_returns_every_published_key(
    publishing_service: JWKPublishingService,
    jwk_service: JWKGenerationService,
) -> None:
    """Набор публичных ключей подписи.

    Given: в кеше опубликованы два ключа подписи — прошлый и текущий,
    When: сервис публикации собирает набор,
    Then: в набор попадают оба ключа.
    """
    # Дано
    previous = await jwk_service.generate_jwk(KEY_TTL_SECONDS)
    current = await jwk_service.generate_jwk(KEY_TTL_SECONDS, overwrite=True)

    # Когда
    keys = await publishing_service.collect()

    # Тогда
    assert {key["kid"] for key in keys} == {previous.key_id, current.key_id}


async def test_collect_returns_empty_sequence_when_nothing_is_published(
    publishing_service: JWKPublishingService,
) -> None:
    """Пустой набор ключей.

    Given: ни один публичный JWK не опубликован,
    When: сервис публикации собирает набор,
    Then: набор пуст — это корректный результат, а не ошибка.
    """
    # Когда
    keys = await publishing_service.collect()

    # Тогда
    assert list(keys) == []


async def test_collect_propagates_cache_failure(
    unavailable_repository: PublicJWKRepository,
) -> None:
    """Отказ кеша публичных ключей.

    Given: Redis с публичными JWK недоступен,
    When: сервис публикации собирает набор,
    Then: ошибка кеша не скрывается от вызывающего кода.
    """
    # Дано
    service = JWKPublishingService(jwk_repository=unavailable_repository)

    # Когда / Тогда
    with pytest.raises(RepositoryError, match="listing error"):
        await service.collect()
