"""Тесты сервиса авторизации запросов по Bearer-токену."""

import pytest

from src.adapters.cache.repositories import RedisRevokedTokensRepository
from src.application import (
    AuthorizationService,
    JWTDecryptionService,
    JWTEncryptionService,
    TokenRevocationService,
)
from src.application.jwk import JWKGenerationService
from src.domain.enums import TokenType
from src.domain.errors import TokenRevokedError, UserAuthorizationError

SUBJECT = 42
TOKEN_ID = "authorization-token-under-test"  # noqa: S105
TTL_SECONDS = 3600


@pytest.fixture
def authorization_service(
    decryption_service: JWTDecryptionService,
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
) -> AuthorizationService:
    """Отдаёт сервис авторизации поверх подмены Redis.

    Args:
        decryption_service (JWTDecryptionService): Сервис проверки токенов.
        blacklisted_tokens_repository (RedisRevokedTokensRepository): Репозиторий
            отозванных токенов поверх подмены Redis.

    Returns:
        AuthorizationService: Сервис авторизации запроса.
    """
    return AuthorizationService(
        decryption_service=decryption_service,
        revocation_service=TokenRevocationService(blacklisted_tokens_repository),
    )


async def _issue_token(
    jwk_service: JWKGenerationService,
    encryption_service: JWTEncryptionService,
    *,
    ttl: int = TTL_SECONDS,
) -> str:
    """Публикует ключ и выпускает access-токен для проверки авторизации.

    Args:
        jwk_service (JWKGenerationService): Сервис генерации и публикации ключей.
        encryption_service (JWTEncryptionService): Сервис выпуска токенов.
        ttl (int, optional): Срок жизни токена в секундах. Defaults to TTL_SECONDS.

    Returns:
        str: Подписанный access-токен.
    """
    await jwk_service.generate_jwk(TTL_SECONDS)
    token, _ = await encryption_service.encrypt(SUBJECT, token_id=TOKEN_ID, ttl=ttl)

    return token


async def test_authorize_requires_token(
    authorization_service: AuthorizationService,
) -> None:
    """Авторизация без Bearer-токена.

    Given: в запросе нет заголовка `Authorization`,
    When: сервис авторизации проверяет запрос,
    Then: он сообщает, что для доступа нужен Bearer-токен.
    """
    # Когда / Тогда
    with pytest.raises(UserAuthorizationError, match="Bearer token is missing"):
        await authorization_service.authorize(None)


async def test_authorize_returns_claims_of_valid_token(
    authorization_service: AuthorizationService,
    jwk_service: JWKGenerationService,
    encryption_service: JWTEncryptionService,
) -> None:
    """Авторизация действующего токена.

    Given: подписанный токен с опубликованным ключом,
    When: сервис авторизации проверяет токен,
    Then: он возвращает проверенные claims токена.
    """
    # Дано
    token = await _issue_token(jwk_service, encryption_service)

    # Когда
    claims = await authorization_service.authorize(token)

    # Тогда
    assert claims["sub"] == str(SUBJECT)
    assert claims["jti"] == TOKEN_ID


async def test_authorize_rejects_revoked_token(
    authorization_service: AuthorizationService,
    jwk_service: JWKGenerationService,
    encryption_service: JWTEncryptionService,
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
) -> None:
    """Авторизация отозванного токена.

    Given: токен уже отозван при выходе,
    When: сервис авторизации проверяет запрос,
    Then: он сообщает, что токен отозван.
    """
    # Дано
    token = await _issue_token(jwk_service, encryption_service)
    await blacklisted_tokens_repository.store(
        token_type=TokenType.ACCESS,
        token_id=TOKEN_ID,
        ttl=TTL_SECONDS,
    )

    # Когда / Тогда
    with pytest.raises(TokenRevokedError, match="Token is revoked"):
        await authorization_service.authorize(token)
