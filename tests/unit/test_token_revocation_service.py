"""Тесты сервиса отзыва токенов."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from src.adapters.cache.repositories import (
    RedisRevokedSessionsRepository,
    RedisRevokedTokensRepository,
    RedisSessionRepository,
)
from src.application import (
    EnsureTokenActive,
    RevokeSession,
    RotateRefreshToken,
)
from src.domain.entities import Session
from src.domain.enums import TokenType
from src.domain.errors import TokenRevokedError
from src.domain.tokens import AccessTokenClaims, RefreshTokenClaims
from tests.doubles import InMemoryRedis

TOKEN_ID = "token-under-test"  # noqa: S105
SID = "session-under-test"
TTL_SECONDS = 3600


def _claims(*, expires_at: int) -> AccessTokenClaims:
    """Собирает `claims` токена для проверок.

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


async def test_ensure_active_accepts_token_that_is_not_revoked(
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
    revoked_sessions_repository: RedisRevokedSessionsRepository,
) -> None:
    """Проверка действующего токена.

    Given: токен не помечен отозванным, When: сервис проверяет его перед аутентификацией, Then:
    проверка проходит без ошибки.

    Args:
        blacklisted_tokens_repository (RedisRevokedTokensRepository): Репозиторий маркеров отзыва
            токенов поверх подмены `Redis`.
        revoked_sessions_repository (RedisRevokedSessionsRepository): Репозиторий маркеров отзыва
            сессий поверх подмены `Redis`.
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

    Given: токен уже отозван при выходе, When: сервис проверяет его перед аутентификацией, Then:
    сервис сообщает, что токен отозван.

    Args:
        blacklisted_tokens_repository (RedisRevokedTokensRepository): Репозиторий маркеров отзыва
            токенов поверх подмены `Redis`.
        revoked_sessions_repository (RedisRevokedSessionsRepository): Репозиторий маркеров отзыва
            сессий поверх подмены `Redis`.
    """
    # Дано
    ensure_token_active = EnsureTokenActive(
        blacklisted_tokens_repository, revoked_sessions_repository
    )
    claims = _claims(expires_at=_expires_in(TTL_SECONDS))
    await blacklisted_tokens_repository.store(TokenType.ACCESS, TOKEN_ID, TTL_SECONDS)

    # Когда / Тогда
    with pytest.raises(TokenRevokedError, match="Token is revoked"):
        await ensure_token_active(claims)


async def test_revoke_session_stores_session_until_it_expires(
    revoked_sessions_repository: RedisRevokedSessionsRepository,
    session_repository: RedisSessionRepository,
    redis_double: InMemoryRedis,
) -> None:
    """Отзыв действующей сессии.

    Given: сервис отзыва сессии и действующий `refresh`-токен, When: сессия отзывается при выходе,
    Then: в `Redis` появляется запись по `sid` с TTL, не превышающим срок жизни токена.

    Args:
        revoked_sessions_repository (RedisRevokedSessionsRepository): Репозиторий маркеров отзыва
            сессий поверх подмены `Redis`.
        session_repository (RedisSessionRepository): Репозиторий сессий поверх подмены `Redis`.
        redis_double (InMemoryRedis): Подмена `Redis` с хранилищем значений и TTL в памяти.
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

    Given: срок действия `refresh`-токена уже истёк, When: сервис пытается отозвать сессию, Then:
    запись не создаётся: проверять отзыв истёкшей сессии бессмысленно.

    Args:
        revoked_sessions_repository (RedisRevokedSessionsRepository): Репозиторий маркеров отзыва
            сессий поверх подмены `Redis`.
        session_repository (RedisSessionRepository): Репозиторий сессий поверх подмены `Redis`.
        redis_double (InMemoryRedis): Подмена `Redis` с хранилищем значений и TTL в памяти.
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

    Given: сессия токена отозвана при выходе, а сам `jti` не отозван, When: сервис проверяет токен
    перед аутентификацией, Then: сервис сообщает, что токен отозван.

    Args:
        blacklisted_tokens_repository (RedisRevokedTokensRepository): Репозиторий маркеров отзыва
            токенов поверх подмены `Redis`.
        revoked_sessions_repository (RedisRevokedSessionsRepository): Репозиторий маркеров отзыва
            сессий поверх подмены `Redis`.
        session_repository (RedisSessionRepository): Репозиторий сессий поверх подмены `Redis`.
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


async def test_rotate_revokes_session_on_refresh_token_reuse(
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
    revoked_sessions_repository: RedisRevokedSessionsRepository,
    session_repository: RedisSessionRepository,
    redis_double: InMemoryRedis,
) -> None:
    """Повторное использование `refresh`-токена отзывает сессию.

    Given: активная сессия и `refresh`-токен, уже ротированный один раз, When: ротация повторяется
    с тем же токеном, Then: сессия помечается отозванной до истечения её срока действия.

    Args:
        blacklisted_tokens_repository (RedisRevokedTokensRepository): Репозиторий маркеров отзыва
            токенов поверх подмены `Redis`.
        revoked_sessions_repository (RedisRevokedSessionsRepository): Репозиторий маркеров отзыва
            сессий поверх подмены `Redis`.
        session_repository (RedisSessionRepository): Репозиторий сессий поверх подмены `Redis`.
        redis_double (InMemoryRedis): Подмена `Redis` с хранилищем значений и TTL в памяти.
    """
    # Дано
    now = datetime.now(UTC)
    await session_repository.save(
        Session(
            id=SID,
            user_id=42,
            created_at=now,
            expires_at=now + timedelta(seconds=TTL_SECONDS),
        )
    )
    rotate = RotateRefreshToken(
        session_repository,
        RevokeSession(revoked_sessions_repository, session_repository),
        blacklisted_tokens_repository,
        revoked_sessions_repository,
        TTL_SECONDS,
    )
    expires_at = _expires_in(TTL_SECONDS)
    claims = RefreshTokenClaims(
        iss="Auth Server",
        sub="42",
        aud="Auth Server",
        iat=expires_at - TTL_SECONDS,
        exp=expires_at,
        jti=TOKEN_ID,
        sid=SID,
    )
    await rotate(claims)

    # Когда / Тогда
    with pytest.raises(TokenRevokedError, match="Token is revoked"):
        await rotate(claims)

    key = f"session:revoked:{SID}"
    assert redis_double.values[key] == "1"
    assert 0 < redis_double.ttl[key] <= TTL_SECONDS

    stored = await session_repository.get(SID)
    assert stored is not None
    assert stored.revoked_at is not None


async def test_concurrent_refresh_consumes_token_once(
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
    revoked_sessions_repository: RedisRevokedSessionsRepository,
    session_repository: RedisSessionRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Два параллельных запроса не могут использовать один refresh-токен дважды."""
    now = datetime.now(UTC)
    await session_repository.save(
        Session(id=SID, user_id=42, created_at=now, expires_at=now + timedelta(seconds=TTL_SECONDS))
    )
    rotate = RotateRefreshToken(
        session_repository,
        RevokeSession(revoked_sessions_repository, session_repository),
        blacklisted_tokens_repository,
        revoked_sessions_repository,
        TTL_SECONDS,
    )
    expires_at = _expires_in(TTL_SECONDS)
    claims = RefreshTokenClaims(
        iss="Auth Server",
        sub="42",
        aud="Auth Server",
        iat=expires_at - TTL_SECONDS,
        exp=expires_at,
        jti=TOKEN_ID,
        sid=SID,
    )

    both_checked = asyncio.Event()
    checked = 0
    request_count = 2
    original_check = revoked_sessions_repository.check

    async def synchronized_check(sid: str) -> bool:
        nonlocal checked
        result = await original_check(sid)
        checked += 1
        if checked == request_count:
            both_checked.set()
        await both_checked.wait()
        return result

    monkeypatch.setattr(revoked_sessions_repository, "check", synchronized_check)

    results = await asyncio.gather(rotate(claims), rotate(claims), return_exceptions=True)

    assert sum(result is None for result in results) == 1
    assert sum(isinstance(result, TokenRevokedError) for result in results) == 1
    assert await revoked_sessions_repository.check(SID)


async def test_rotation_rejects_missing_or_revoked_session(
    session_repository: RedisSessionRepository,
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
    revoked_sessions_repository: RedisRevokedSessionsRepository,
) -> None:
    """Продление не создаёт заново закрытую или исчезнувшую сессию."""
    rotate = RotateRefreshToken(
        session_repository,
        RevokeSession(revoked_sessions_repository, session_repository),
        blacklisted_tokens_repository,
        revoked_sessions_repository,
        TTL_SECONDS,
    )
    expires_at = _expires_in(TTL_SECONDS)
    claims = RefreshTokenClaims(
        iss="Auth Server",
        sub="42",
        aud="Auth Server",
        iat=expires_at - TTL_SECONDS,
        exp=expires_at,
        jti=TOKEN_ID,
        sid=SID,
    )
    with pytest.raises(TokenRevokedError):
        await rotate(claims)

    now = datetime.now(UTC)
    await session_repository.save(
        Session(
            id=SID,
            user_id=42,
            created_at=now,
            expires_at=now + timedelta(seconds=TTL_SECONDS),
            revoked_at=now,
        )
    )
    claims["jti"] = "another-token"
    with pytest.raises(TokenRevokedError):
        await rotate(claims)
    stored = await session_repository.get(SID)
    assert stored is not None
    assert stored.revoked_at is not None
