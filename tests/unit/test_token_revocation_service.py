"""Тесты сервиса отзыва токенов."""

from datetime import UTC, datetime

import pytest

from src.adapters.cache.repositories import (
    RedisRevokedSessionsRepository,
    RedisRevokedTokensRepository,
    RedisSessionRepository,
)
from src.application import EnsureTokenActive, RevokeSession, RevokeToken
from src.domain.errors import TokenRevokedError
from src.domain.tokens import AccessTokenClaims
from tests.doubles import InMemoryRedis

TOKEN_ID = "token-under-test"  # noqa: S105
SID = "session-under-test"
TTL_SECONDS = 3600


def _claims(*, expires_at: int) -> AccessTokenClaims:
    """Собирает claims токена для проверок.

    Args:
        expires_at (int): Момент истечения токена в секундах Unix epoch.

    Returns:
        AccessTokenClaims: Claims токена с заданным сроком действия.
    """
    return AccessTokenClaims(
        iss="Auth Server",
        sub="42",
        aud="Airsoft Prim",
        iat=expires_at - TTL_SECONDS,
        exp=expires_at,
        jti=TOKEN_ID,
        sid=SID,
    )


def _expires_in(seconds: int) -> int:
    """Возвращает момент истечения через заданное число секунд.

    Args:
        seconds (int): Сколько секунд остаётся до истечения.

    Returns:
        int: Момент истечения в секундах Unix epoch.
    """
    return int(datetime.now(UTC).timestamp()) + seconds


async def test_revoke_stores_token_until_it_expires(
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
    redis_double: InMemoryRedis,
) -> None:
    """Отзыв действующего токена.

    Given: сервис отзыва и действующий access-токен,
    When: токен отзывается при выходе,
    Then: в Redis появляется запись по `jti` с TTL, не превышающим срок жизни токена.
    """
    # Дано
    revoke_token = RevokeToken(blacklisted_tokens_repository)
    claims = _claims(expires_at=_expires_in(TTL_SECONDS))

    # Когда
    await revoke_token(claims)

    # Тогда
    key = f"token:access:revoked:{TOKEN_ID}"
    assert redis_double.values[key] == "1"
    assert 0 < redis_double.ttl[key] <= TTL_SECONDS


async def test_revoke_does_not_store_expired_token(
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
    redis_double: InMemoryRedis,
) -> None:
    """Отзыв уже истёкшего токена.

    Given: срок действия токена уже истёк,
    When: сервис пытается отозвать токен,
    Then: запись не создаётся: проверять отзыв истёкшего токена бессмысленно.
    """
    # Дано
    revoke_token = RevokeToken(blacklisted_tokens_repository)
    claims = _claims(expires_at=_expires_in(-TTL_SECONDS))

    # Когда
    await revoke_token(claims)

    # Тогда
    assert redis_double.values == {}


async def test_ensure_active_accepts_token_that_is_not_revoked(
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
    revoked_sessions_repository: RedisRevokedSessionsRepository,
) -> None:
    """Проверка действующего токена.

    Given: токен не помечен отозванным,
    When: сервис проверяет его перед аутентификацией,
    Then: проверка проходит без ошибки.
    """
    # Дано
    ensure_token_active = EnsureTokenActive(
        blacklisted_tokens_repository, revoked_sessions_repository
    )
    claims = _claims(expires_at=_expires_in(TTL_SECONDS))

    # Когда / Тогда
    await ensure_token_active(claims)


async def test_ensure_active_rejects_revoked_token(
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
    revoked_sessions_repository: RedisRevokedSessionsRepository,
) -> None:
    """Проверка отозванного токена.

    Given: токен уже отозван при выходе,
    When: сервис проверяет его перед аутентификацией,
    Then: сервис сообщает, что токен отозван.
    """
    # Дано
    revoke_token = RevokeToken(blacklisted_tokens_repository)
    ensure_token_active = EnsureTokenActive(
        blacklisted_tokens_repository, revoked_sessions_repository
    )
    claims = _claims(expires_at=_expires_in(TTL_SECONDS))
    await revoke_token(claims)

    # Когда / Тогда
    with pytest.raises(TokenRevokedError, match="Token is revoked"):
        await ensure_token_active(claims)


async def test_revoke_session_stores_session_until_it_expires(
    revoked_sessions_repository: RedisRevokedSessionsRepository,
    session_repository: RedisSessionRepository,
    redis_double: InMemoryRedis,
) -> None:
    """Отзыв действующей сессии.

    Given: сервис отзыва сессии и действующий refresh-токен,
    When: сессия отзывается при выходе,
    Then: в Redis появляется запись по `sid` с TTL, не превышающим срок жизни токена.
    """
    # Дано
    revoke_session = RevokeSession(revoked_sessions_repository, session_repository)
    claims = _claims(expires_at=_expires_in(TTL_SECONDS))

    # Когда
    await revoke_session(claims)

    # Тогда
    key = f"session:revoked:{SID}"
    assert redis_double.values[key] == "1"
    assert 0 < redis_double.ttl[key] <= TTL_SECONDS


async def test_revoke_session_does_not_store_expired_session(
    revoked_sessions_repository: RedisRevokedSessionsRepository,
    session_repository: RedisSessionRepository,
    redis_double: InMemoryRedis,
) -> None:
    """Отзыв уже истёкшей сессии.

    Given: срок действия refresh-токена уже истёк,
    When: сервис пытается отозвать сессию,
    Then: запись не создаётся: проверять отзыв истёкшей сессии бессмысленно.
    """
    # Дано
    revoke_session = RevokeSession(revoked_sessions_repository, session_repository)
    claims = _claims(expires_at=_expires_in(-TTL_SECONDS))

    # Когда
    await revoke_session(claims)

    # Тогда
    assert redis_double.values == {}


async def test_ensure_active_rejects_revoked_session(
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
    revoked_sessions_repository: RedisRevokedSessionsRepository,
    session_repository: RedisSessionRepository,
) -> None:
    """Проверка токена отозванной сессии.

    Given: сессия токена отозвана при выходе, а сам `jti` не отозван,
    When: сервис проверяет токен перед аутентификацией,
    Then: сервис сообщает, что токен отозван.
    """
    # Дано
    revoke_session = RevokeSession(revoked_sessions_repository, session_repository)
    ensure_token_active = EnsureTokenActive(
        blacklisted_tokens_repository, revoked_sessions_repository
    )
    claims = _claims(expires_at=_expires_in(TTL_SECONDS))
    await revoke_session(claims)

    # Когда / Тогда
    with pytest.raises(TokenRevokedError, match="Token is revoked"):
        await ensure_token_active(claims)
