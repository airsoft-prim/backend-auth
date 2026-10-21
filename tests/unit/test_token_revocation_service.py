"""Тесты сервиса отзыва токенов."""

from datetime import UTC, datetime

import pytest

from src.general.security import AccessTokenClaims
from src.providers.cache.repositories import RevokedTokensRepository
from src.services import TokenRevocationService, TokenRevokedError
from tests.doubles import InMemoryRedis

TOKEN_ID = "token-under-test"  # noqa: S105
TTL_SECONDS = 3600


def _claims(*, expires_at: int) -> AccessTokenClaims:
    """Собирает claims токена для проверок.

    Args:
        expires_at (int): Момент истечения токена в секундах Unix epoch.

    Returns:
        AccessTokenClaims: Claims токена с заданным сроком действия.
    """
    return {
        "iss": "Auth Server",
        "sub": "42",
        "aud": "Airsoft Prim",
        "iat": expires_at - TTL_SECONDS,
        "exp": expires_at,
        "jti": TOKEN_ID,
    }


def _expires_in(seconds: int) -> int:
    """Возвращает момент истечения через заданное число секунд.

    Args:
        seconds (int): Сколько секунд остаётся до истечения.

    Returns:
        int: Момент истечения в секундах Unix epoch.
    """
    return int(datetime.now(UTC).timestamp()) + seconds


async def test_revoke_stores_token_until_it_expires(
    blacklisted_tokens_repository: RevokedTokensRepository,
    redis_double: InMemoryRedis,
) -> None:
    """Отзыв действующего токена.

    Given: сервис отзыва и действующий access-токен,
    When: токен отзывается при выходе,
    Then: в Redis появляется запись по `jti` с TTL, не превышающим срок жизни токена.
    """
    # Дано
    service = TokenRevocationService(blacklisted_tokens_repository)
    claims = _claims(expires_at=_expires_in(TTL_SECONDS))

    # Когда
    await service.revoke(claims)

    # Тогда
    key = f"token:access:revoked:{TOKEN_ID}"
    assert redis_double.values[key] == "1"
    assert 0 < redis_double.ttl[key] <= TTL_SECONDS


async def test_revoke_does_not_store_expired_token(
    blacklisted_tokens_repository: RevokedTokensRepository,
    redis_double: InMemoryRedis,
) -> None:
    """Отзыв уже истёкшего токена.

    Given: срок действия токена уже истёк,
    When: сервис пытается отозвать токен,
    Then: запись не создаётся: проверять отзыв истёкшего токена бессмысленно.
    """
    # Дано
    service = TokenRevocationService(blacklisted_tokens_repository)
    claims = _claims(expires_at=_expires_in(-TTL_SECONDS))

    # Когда
    await service.revoke(claims)

    # Тогда
    assert redis_double.values == {}


async def test_ensure_active_accepts_token_that_is_not_revoked(
    blacklisted_tokens_repository: RevokedTokensRepository,
) -> None:
    """Проверка действующего токена.

    Given: токен не помечен отозванным,
    When: сервис проверяет его перед аутентификацией,
    Then: проверка проходит без ошибки.
    """
    # Дано
    service = TokenRevocationService(blacklisted_tokens_repository)
    claims = _claims(expires_at=_expires_in(TTL_SECONDS))

    # Когда / Тогда
    await service.ensure_active(claims)


async def test_ensure_active_rejects_revoked_token(
    blacklisted_tokens_repository: RevokedTokensRepository,
) -> None:
    """Проверка отозванного токена.

    Given: токен уже отозван при выходе,
    When: сервис проверяет его перед аутентификацией,
    Then: сервис сообщает, что токен отозван.
    """
    # Дано
    service = TokenRevocationService(blacklisted_tokens_repository)
    claims = _claims(expires_at=_expires_in(TTL_SECONDS))
    await service.revoke(claims)

    # Когда / Тогда
    with pytest.raises(TokenRevokedError, match="Token is revoked"):
        await service.ensure_active(claims)
