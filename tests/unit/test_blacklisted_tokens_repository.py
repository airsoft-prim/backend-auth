"""Тесты репозитория отозванных токенов в Redis."""

import pytest

from src.adapters.cache.repositories import RedisRevokedTokensRepository
from src.domain.enums import TokenType
from src.domain.errors import RepositoryError
from tests.doubles import InMemoryRedis, as_redis

TOKEN_ID = "token-under-test"  # noqa: S105
TTL_SECONDS = 3600


async def test_store_writes_token_under_type_and_jti(
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
    redis_double: InMemoryRedis,
) -> None:
    """Сохранение отозванного токена.

    Given: репозиторий и токен доступа,
    When: токен помечается отозванным,
    Then: в Redis появляется ключ с типом и `jti`, а запись ограничена остатком срока жизни.
    """
    # Дано
    key = f"token:access:revoked:{TOKEN_ID}"

    # Когда
    await blacklisted_tokens_repository.store(TokenType.ACCESS, TOKEN_ID, TTL_SECONDS)

    # Тогда
    assert redis_double.values[key] == "1"
    assert redis_double.ttl[key] == TTL_SECONDS


async def test_contains_reports_stored_token(
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
) -> None:
    """Проверка отозванного токена.

    Given: токен помечен отозванным,
    When: репозиторий проверяет этот токен,
    Then: он сообщает, что токен отозван.
    """
    # Дано
    await blacklisted_tokens_repository.store(TokenType.ACCESS, TOKEN_ID, TTL_SECONDS)

    # Когда
    is_blacklisted = await blacklisted_tokens_repository.check(TokenType.ACCESS, TOKEN_ID)

    # Тогда
    assert is_blacklisted is True


async def test_contains_reports_token_that_was_not_stored(
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
) -> None:
    """Проверка действующего токена.

    Given: токен не помечался отозванным,
    When: репозиторий проверяет этот токен,
    Then: он сообщает, что токен действует.
    """
    # Когда
    is_blacklisted = await blacklisted_tokens_repository.check(TokenType.ACCESS, TOKEN_ID)

    # Тогда
    assert is_blacklisted is False


async def test_access_and_refresh_tokens_with_same_id_are_independent(
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
) -> None:
    """Разделение пространств access- и refresh-токенов.

    Given: отозван access-токен с некоторым `jti`,
    When: репозиторий проверяет refresh-токен с тем же `jti`,
    Then: refresh-токен считается действующим: типы токенов не пересекаются.
    """
    # Дано
    await blacklisted_tokens_repository.store(TokenType.ACCESS, TOKEN_ID, TTL_SECONDS)

    # Когда
    refresh_is_blacklisted = await blacklisted_tokens_repository.check(TokenType.REFRESH, TOKEN_ID)

    # Тогда
    assert refresh_is_blacklisted is False


def test_compile_template_builds_key_with_type_and_jti(
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
) -> None:
    """Сборка ключа Redis из шаблона.

    Given: шаблон ключа блэклиста,
    When: шаблон собирается с типом и `jti`,
    Then: ключ получает вид `token:<access|refresh>:revoked:<jti>`.
    """
    # Когда / Тогда
    key = blacklisted_tokens_repository.compile_template(
        {"type": TokenType.ACCESS.value, "jti": TOKEN_ID}
    )

    assert key == f"token:access:revoked:{TOKEN_ID}"


async def test_store_translates_transport_failure_into_repository_error() -> None:
    """Отказ транспорта Redis при записи.

    Given: Redis недоступен,
    When: репозиторий помечает токен отозванным,
    Then: ошибка транспорта превращается в ошибку репозитория с понятным текстом.
    """
    # Дано
    repository = RedisRevokedTokensRepository(as_redis(InMemoryRedis(unavailable=True)))

    # Когда / Тогда
    with pytest.raises(RepositoryError, match="saving error"):
        await repository.store(TokenType.ACCESS, TOKEN_ID, TTL_SECONDS)


async def test_contains_translates_transport_failure_into_repository_error() -> None:
    """Отказ транспорта Redis при чтении.

    Given: Redis недоступен,
    When: репозиторий проверяет отзыв токена,
    Then: ошибка транспорта превращается в ошибку репозитория с понятным текстом.
    """
    # Дано
    repository = RedisRevokedTokensRepository(as_redis(InMemoryRedis(unavailable=True)))

    # Когда / Тогда
    with pytest.raises(RepositoryError, match="getting error"):
        await repository.check(TokenType.ACCESS, TOKEN_ID)
