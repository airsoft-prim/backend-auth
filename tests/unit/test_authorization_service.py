"""Тесты сервиса авторизации запросов по Bearer-токену."""

import pytest

from src.adapters.cache.repositories import RedisRevokedTokensRepository
from src.application import (
    Authorize,
    EnsureTokenActive,
    IssueAccessToken,
    VerifyAccessToken,
)
from src.application.jwk import RotateJwk
from src.domain.enums import TokenType
from src.domain.errors import TokenRevokedError, UserAuthorizationError

SUBJECT = 42
TOKEN_ID = "authorization-token-under-test"  # noqa: S105
TTL_SECONDS = 3600


@pytest.fixture
def authorize(
    verify_access_token: VerifyAccessToken,
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
) -> Authorize:
    """Отдаёт use case авторизации поверх подмены Redis.

    Args:
        verify_access_token (VerifyAccessToken): Use case проверки токенов.
        blacklisted_tokens_repository (RedisRevokedTokensRepository): Репозиторий
            отозванных токенов поверх подмены Redis.

    Returns:
        Authorize: Use case авторизации запроса.
    """
    ensure_active = EnsureTokenActive(blacklisted_tokens_repository)
    return Authorize(verify_access_token, ensure_active)


async def _issue_token(
    rotate_jwk: RotateJwk,
    issue_access_token: IssueAccessToken,
    *,
    ttl: int = TTL_SECONDS,
) -> str:
    """Публикует ключ и выпускает access-токен для проверки авторизации.

    Args:
        rotate_jwk (RotateJwk): Use case генерации и публикации ключей.
        issue_access_token (IssueAccessToken): Use case выпуска токенов.
        ttl (int, optional): Срок жизни токена в секундах. Defaults to TTL_SECONDS.

    Returns:
        str: Подписанный access-токен.
    """
    await rotate_jwk(TTL_SECONDS)
    token, _ = await issue_access_token(SUBJECT, token_id=TOKEN_ID, ttl=ttl)

    return token


async def test_authorize_requires_token(
    authorize: Authorize,
) -> None:
    """Авторизация без Bearer-токена.

    Given: в запросе нет заголовка `Authorization`,
    When: сервис авторизации проверяет запрос,
    Then: он сообщает, что для доступа нужен Bearer-токен.
    """
    # Когда / Тогда
    with pytest.raises(UserAuthorizationError, match="Bearer token is missing"):
        await authorize(None)


async def test_authorize_returns_claims_of_valid_token(
    authorize: Authorize,
    rotate_jwk: RotateJwk,
    issue_access_token: IssueAccessToken,
) -> None:
    """Авторизация действующего токена.

    Given: подписанный токен с опубликованным ключом,
    When: сервис авторизации проверяет токен,
    Then: он возвращает проверенные claims токена.
    """
    # Дано
    token = await _issue_token(rotate_jwk, issue_access_token)

    # Когда
    claims = await authorize(token)

    # Тогда
    assert claims["sub"] == str(SUBJECT)
    assert claims["jti"] == TOKEN_ID


async def test_authorize_rejects_revoked_token(
    authorize: Authorize,
    rotate_jwk: RotateJwk,
    issue_access_token: IssueAccessToken,
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
) -> None:
    """Авторизация отозванного токена.

    Given: токен уже отозван при выходе,
    When: сервис авторизации проверяет запрос,
    Then: он сообщает, что токен отозван.
    """
    # Дано
    token = await _issue_token(rotate_jwk, issue_access_token)
    await blacklisted_tokens_repository.store(
        token_type=TokenType.ACCESS,
        token_id=TOKEN_ID,
        ttl=TTL_SECONDS,
    )

    # Когда / Тогда
    with pytest.raises(TokenRevokedError, match="Token is revoked"):
        await authorize(token)
