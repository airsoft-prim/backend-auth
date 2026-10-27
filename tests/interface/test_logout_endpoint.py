"""Тесты HTTP-контракта выхода из системы."""

from fastapi import FastAPI, status
import pytest

from src.adapters.cache.repositories import RedisRevokedTokensRepository
from src.application import JWTDecryptionService, JWTEncryptionService, TokenRevocationService
from src.application.jwk import JWKGenerationService
from src.interface.auth.deps import get_decryption_service, get_token_revocation_service
from tests.asgi_client import ASGIClient
from tests.doubles import InMemoryRedis

LOGOUT_PATH = "/auth/logout"
SUBJECT = 42
TOKEN_ID = "logout-token-under-test"  # noqa: S105
TTL_SECONDS = 3600


@pytest.fixture
def logout_client(
    api_app: FastAPI,
    decryption_service: JWTDecryptionService,
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
) -> ASGIClient:
    """Отдаёт клиент выхода с подменой проверки токена и хранилища отзыва.

    Args:
        api_app (FastAPI): Приложение под тестом.
        decryption_service (JWTDecryptionService): Сервис проверки токенов поверх
            подмены Redis с опубликованными JWK.
        blacklisted_tokens_repository (RedisRevokedTokensRepository): Репозиторий
            отозванных токенов поверх подмены Redis.

    Returns:
        ASGIClient: Клиент маршрута выхода.
    """
    api_app.dependency_overrides[get_decryption_service] = lambda: decryption_service
    api_app.dependency_overrides[get_token_revocation_service] = lambda: TokenRevocationService(
        blacklisted_tokens_repository
    )

    return ASGIClient(api_app)


async def _issue_token(
    jwk_service: JWKGenerationService,
    encryption_service: JWTEncryptionService,
    *,
    ttl: int = TTL_SECONDS,
) -> str:
    """Публикует ключ и выпускает access-токен для проверки выхода.

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


def _authorization(token: str) -> dict[str, str]:
    """Собирает заголовок авторизации с Bearer-токеном.

    Args:
        token (str): Access-токен.

    Returns:
        dict[str, str]: Заголовок `Authorization`.
    """
    return {"Authorization": f"Bearer {token}"}


async def test_logout_revokes_token_and_returns_no_content(
    logout_client: ASGIClient,
    jwk_service: JWKGenerationService,
    encryption_service: JWTEncryptionService,
    redis_double: InMemoryRedis,
) -> None:
    """Выход с действующим токеном.

    Given: клиент с действующим access-токеном,
    When: он завершает сессию,
    Then: приходит 204 без тела, а токен попадает в блэклист до конца срока действия.
    """
    # Дано
    token = await _issue_token(jwk_service, encryption_service)

    # Когда
    response = await logout_client.post(LOGOUT_PATH, headers=_authorization(token))

    # Тогда
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.body == b""
    assert "content-type" not in response.headers

    key = f"token:access:revoked:{TOKEN_ID}"
    assert redis_double.values[key] == "1"
    assert 0 < redis_double.ttl[key] <= TTL_SECONDS


async def test_logout_rejects_already_revoked_token(
    logout_client: ASGIClient,
    jwk_service: JWKGenerationService,
    encryption_service: JWTEncryptionService,
) -> None:
    """Повторный выход с тем же токеном.

    Given: токен уже отозван предыдущим выходом,
    When: клиент повторяет выход с этим токеном,
    Then: приходит 403: отозванный токен больше не принимается.
    """
    # Дано
    token = await _issue_token(jwk_service, encryption_service)
    await logout_client.post(LOGOUT_PATH, headers=_authorization(token))

    # Когда
    response = await logout_client.post(LOGOUT_PATH, headers=_authorization(token))

    # Тогда
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.payload == {
        "message": "Authorization failed.",
        "details": "Provided credentials are invalid.",
    }


async def test_logout_requires_bearer_token(logout_client: ASGIClient) -> None:
    """Выход без заголовка авторизации.

    Given: запрос без заголовка `Authorization`,
    When: клиент пытается завершить сессию,
    Then: приходит 401 с требованием Bearer-аутентификации.
    """
    # Когда
    response = await logout_client.post(LOGOUT_PATH)

    # Тогда
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.payload == {
        "message": "Authorization failed.",
        "details": "Bearer token is missing.",
    }


async def test_logout_rejects_invalid_token(
    logout_client: ASGIClient,
) -> None:
    """Выход с невалидным токеном.

    Given: в заголовке передана строка, не являющаяся JWT,
    When: клиент пытается завершить сессию,
    Then: приходит 403: токен не проходит проверку.
    """
    # Когда
    response = await logout_client.post(LOGOUT_PATH, headers=_authorization("not-a-jwt"))

    # Тогда
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.payload["message"] == "Authorization failed."


async def test_logout_rejects_expired_token(
    logout_client: ASGIClient,
    jwk_service: JWKGenerationService,
    encryption_service: JWTEncryptionService,
) -> None:
    """Выход с просроченным токеном.

    Given: срок действия токена уже истёк,
    When: клиент пытается завершить сессию,
    Then: приходит 403: просроченный токен не принимается.
    """
    # Дано
    token = await _issue_token(jwk_service, encryption_service, ttl=-1)

    # Когда
    response = await logout_client.post(LOGOUT_PATH, headers=_authorization(token))

    # Тогда
    assert response.status_code == status.HTTP_403_FORBIDDEN
