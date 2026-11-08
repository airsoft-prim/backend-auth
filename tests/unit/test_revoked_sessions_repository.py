"""Тесты репозитория отозванных сессий в `Redis`."""

import pytest

from src.adapters.cache.repositories import RedisRevokedSessionsRepository
from src.domain.errors import RepositoryError
from tests.doubles import InMemoryRedis, as_redis

SID = "session-under-test"
TTL_SECONDS = 3600


async def test_store_writes_session_key_with_ttl(
    revoked_sessions_repository: RedisRevokedSessionsRepository,
    redis_double: InMemoryRedis,
) -> None:
    """Сохранение отозванной сессии.

    Given: репозиторий и сессия, When: сессия помечается отозванной, Then: в `Redis` появляется
    ключ `session:revoked:<sid>`, а запись ограничена остатком срока жизни.

    Args:
        revoked_sessions_repository (RedisRevokedSessionsRepository): Репозиторий маркеров отзыва
            сессий поверх подмены `Redis`.
        redis_double (InMemoryRedis): Подмена `Redis` с хранилищем значений и TTL в памяти.
    """
    # Дано
    key = f"session:revoked:{SID}"

    # Когда
    await revoked_sessions_repository.store(SID, TTL_SECONDS)

    # Тогда
    assert redis_double.values[key] == "1"
    assert redis_double.ttl[key] == TTL_SECONDS


async def test_check_reports_stored_session(
    revoked_sessions_repository: RedisRevokedSessionsRepository,
) -> None:
    """Проверка отозванной сессии.

    Given: сессия помечена отозванной, When: репозиторий проверяет эту сессию, Then: он сообщает,
    что сессия отозвана.

    Args:
        revoked_sessions_repository (RedisRevokedSessionsRepository): Репозиторий маркеров отзыва
            сессий поверх подмены `Redis`.
    """
    # Дано
    await revoked_sessions_repository.store(SID, TTL_SECONDS)

    # Когда
    is_revoked = await revoked_sessions_repository.check(SID)

    # Тогда
    assert is_revoked is True


async def test_check_reports_session_that_was_not_stored(
    revoked_sessions_repository: RedisRevokedSessionsRepository,
) -> None:
    """Проверка действующей сессии.

    Given: сессия не помечалась отозванной, When: репозиторий проверяет эту сессию, Then: он
    сообщает, что сессия действует.

    Args:
        revoked_sessions_repository (RedisRevokedSessionsRepository): Репозиторий маркеров отзыва
            сессий поверх подмены `Redis`.
    """
    # Когда
    is_revoked = await revoked_sessions_repository.check(SID)

    # Тогда
    assert is_revoked is False


async def test_store_translates_transport_failure_into_repository_error() -> None:
    """Отказ транспорта `Redis` при записи.

    Given: `Redis` недоступен, When: репозиторий помечает сессию отозванной, Then: ошибка
    транспорта превращается в ошибку репозитория с понятным текстом.
    """
    # Дано
    repository = RedisRevokedSessionsRepository(as_redis(InMemoryRedis(unavailable=True)))

    # Когда / Тогда
    with pytest.raises(RepositoryError, match="saving error"):
        await repository.store(SID, TTL_SECONDS)


async def test_check_translates_transport_failure_into_repository_error() -> None:
    """Отказ транспорта `Redis` при чтении.

    Given: `Redis` недоступен, When: репозиторий проверяет отзыв сессии, Then: ошибка транспорта
    превращается в ошибку репозитория с понятным текстом.
    """
    # Дано
    repository = RedisRevokedSessionsRepository(as_redis(InMemoryRedis(unavailable=True)))

    # Когда / Тогда
    with pytest.raises(RepositoryError, match="getting error"):
        await repository.check(SID)
