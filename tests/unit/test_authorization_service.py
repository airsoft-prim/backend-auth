"""Тесты сервиса авторизации запросов по Bearer-токену."""

import jwt
import pytest

from src.adapters.cache.repositories import (
    RedisRevokedSessionsRepository,
    RedisRevokedTokensRepository,
)
from src.application import (
    Authorize,
    EnsureTokenActive,
    SignToken,
    VerifyToken,
)
from src.application.jwk import RotateJwk
from src.domain.enums import TokenType
from src.domain.errors import TokenRevokedError, UserAuthorizationError

SUBJECT = 42
SUBJECT_ROLE = "user"
SID = "session-under-test"
TTL_SECONDS = 3600


@pytest.fixture
def authorize(
    verify_token: VerifyToken,
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
    revoked_sessions_repository: RedisRevokedSessionsRepository,
) -> Authorize:
    """Отдаёт use case авторизации поверх подмены `Redis`.

    Args:
        verify_token (VerifyToken): Use case проверки токенов.
        blacklisted_tokens_repository (RedisRevokedTokensRepository): Репозиторий отозванных
            токенов поверх подмены `Redis`.
        revoked_sessions_repository (RedisRevokedSessionsRepository): Репозиторий отозванных сессий
            поверх подмены `Redis`.

    Returns:
        Authorize: Use case авторизации запроса.
    """
    ensure_active = EnsureTokenActive(blacklisted_tokens_repository, revoked_sessions_repository)
    return Authorize(verify_token, ensure_active)


async def _issue_token(
    rotate_jwk: RotateJwk,
    sign_token: SignToken,
) -> str:
    """Публикует ключ и выпускает `access`-токен для проверки авторизации.

    Args:
        rotate_jwk (RotateJwk): Use case генерации и публикации ключей.
        sign_token (SignToken): Use case выпуска токенов.

    Returns:
        str: Подписанный `access`-токен.
    """
    await rotate_jwk(TTL_SECONDS)
    token, _ = await sign_token(SUBJECT, SID, not_required={"srl": SUBJECT_ROLE})

    return token


def _token_jti(token: str) -> str:
    """Возвращает `jti` токена без проверки подписи.

    Args:
        token (str): Подписанный JWT.

    Returns:
        str: Идентификатор токена (`jti`).
    """
    return jwt.decode(token, options={"verify_signature": False})["jti"]


async def test_authorize_requires_token(
    authorize: Authorize,
) -> None:
    """Авторизация без Bearer-токена.

    Given: в запросе нет заголовка `Authorization`, When: сервис авторизации проверяет запрос,
    Then: он сообщает, что для доступа нужен Bearer-токен.

    Args:
        authorize (Authorize): Сценарий авторизации с тестовыми зависимостями.
    """
    # Когда / Тогда
    with pytest.raises(UserAuthorizationError, match="Bearer token is missing"):
        await authorize(None)


async def test_authorize_returns_claims_of_valid_token(
    authorize: Authorize,
    rotate_jwk: RotateJwk,
    sign_token: SignToken,
) -> None:
    """Авторизация действующего токена.

    Given: подписанный токен с опубликованным ключом, When: сервис авторизации проверяет токен,
    Then: он возвращает проверенные `claims` токена.

    Args:
        authorize (Authorize): Сценарий авторизации с тестовыми зависимостями.
        rotate_jwk (RotateJwk): Сценарий ротации ключей с тестовыми хранилищами.
        sign_token (SignToken): Сценарий подписи `access`-токена ключом тестового хранилища.
    """
    # Дано
    token = await _issue_token(rotate_jwk, sign_token)

    # Когда
    claims = await authorize(token)

    # Тогда
    assert claims["sub"] == str(SUBJECT)
    assert claims["jti"]


async def test_authorize_rejects_revoked_token(
    authorize: Authorize,
    rotate_jwk: RotateJwk,
    sign_token: SignToken,
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
) -> None:
    """Авторизация отозванного токена.

    Given: токен уже отозван при выходе, When: сервис авторизации проверяет запрос, Then: он
    сообщает, что токен отозван.

    Args:
        authorize (Authorize): Сценарий авторизации с тестовыми зависимостями.
        rotate_jwk (RotateJwk): Сценарий ротации ключей с тестовыми хранилищами.
        sign_token (SignToken): Сценарий подписи `access`-токена ключом тестового хранилища.
        blacklisted_tokens_repository (RedisRevokedTokensRepository): Репозиторий маркеров отзыва
            токенов поверх подмены `Redis`.
    """
    # Дано
    token = await _issue_token(rotate_jwk, sign_token)
    await blacklisted_tokens_repository.store(
        token_type=TokenType.ACCESS,
        token_id=_token_jti(token),
        ttl=TTL_SECONDS,
    )

    # Когда / Тогда
    with pytest.raises(TokenRevokedError, match="Token is revoked"):
        await authorize(token)
