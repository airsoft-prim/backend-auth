"""Тесты публикации публичных JWK."""

import pytest

from src.adapters.cache.repositories import RedisPublicJwkRepository
from src.application.jwk import CollectJwks, RotateJwk
from src.domain.errors import RepositoryError

KEY_TTL_SECONDS = 3600


async def test_collect_returns_every_published_key(
    collect_jwks: CollectJwks,
    rotate_jwk: RotateJwk,
) -> None:
    """Набор публичных ключей подписи.

    Given: в кеше опубликованы два ключа подписи — прошлый и текущий, When: сервис публикации
    собирает набор, Then: в набор попадают оба ключа.

    Args:
        collect_jwks (CollectJwks): Сценарий чтения опубликованных публичных JWK.
        rotate_jwk (RotateJwk): Сценарий ротации ключей с тестовыми хранилищами.
    """
    # Дано
    previous = await rotate_jwk(KEY_TTL_SECONDS)
    current = await rotate_jwk(KEY_TTL_SECONDS, overwrite=True)

    # Когда
    keys = await collect_jwks()

    # Тогда
    assert {key["kid"] for key in keys} == {previous.key_id, current.key_id}


async def test_collect_returns_empty_sequence_when_nothing_is_published(
    collect_jwks: CollectJwks,
) -> None:
    """Пустой набор ключей.

    Given: ни один публичный JWK не опубликован, When: сервис публикации собирает набор, Then:
    набор пуст — это корректный результат, а не ошибка.

    Args:
        collect_jwks (CollectJwks): Сценарий чтения опубликованных публичных JWK.
    """
    # Когда
    keys = await collect_jwks()

    # Тогда
    assert list(keys) == []


async def test_collect_propagates_cache_failure(
    unavailable_repository: RedisPublicJwkRepository,
) -> None:
    """Отказ кеша публичных ключей.

    Given: `Redis` с публичными JWK недоступен, When: сервис публикации собирает набор, Then:
    ошибка кеша не скрывается от вызывающего кода.

    Args:
        unavailable_repository (RedisPublicJwkRepository): Репозиторий JWK с подменой недоступного
            `Redis`.
    """
    # Дано
    collect_jwks = CollectJwks(jwks=unavailable_repository)

    # Когда / Тогда
    with pytest.raises(RepositoryError, match="listing error"):
        await collect_jwks()
