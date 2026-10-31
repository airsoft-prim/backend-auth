"""Тесты HTTP-контракта выхода из системы."""

from fastapi import FastAPI, status
import jwt
import pytest

from src.adapters.cache.repositories import RedisRevokedTokensRepository
from src.adapters.filesystem.repositories import FilePrivateJwkRepository
from src.application import EnsureTokenActive, RevokeToken, SignToken, VerifyToken
from src.application.jwk import RotateJwk
from src.config import config
from src.domain.tokens import AccessTokenConfig
from src.interface.auth.deps import (
    get_ensure_token_active,
    get_revoke_token,
    get_verify_token,
)
from tests.asgi_client import ASGIClient
from tests.doubles import InMemoryRedis

LOGOUT_PATH = "/auth/logout"
SUBJECT = 42
SUBJECT_ROLE = "user"
SID = "session-under-test"
TTL_SECONDS = 3600


@pytest.fixture
def logout_client(
    api_app: FastAPI,
    verify_token: VerifyToken,
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
) -> ASGIClient:
    """Отдаёт клиент выхода с подменой проверки токена и хранилища отзыва.

    Args:
        api_app (FastAPI): Приложение под тестом.
        verify_token (VerifyToken): Use case проверки токенов поверх
            подмены Redis с опубликованными JWK.
        blacklisted_tokens_repository (RedisRevokedTokensRepository): Репозиторий
            отозванных токенов поверх подмены Redis.

    Returns:
        ASGIClient: Клиент маршрута выхода.
    """
    api_app.dependency_overrides[get_verify_token] = lambda: verify_token
    api_app.dependency_overrides[get_ensure_token_active] = lambda: EnsureTokenActive(
        blacklisted_tokens_repository
    )
    api_app.dependency_overrides[get_revoke_token] = lambda: RevokeToken(
        blacklisted_tokens_repository
    )

    return ASGIClient(api_app)


async def _issue_token(
    rotate_jwk: RotateJwk,
    sign_token: SignToken,
) -> str:
    """Публикует ключ и выпускает access-токен для проверки выхода.

    Args:
        rotate_jwk (RotateJwk): Use case генерации и публикации ключей.
        sign_token (SignToken): Use case выпуска токенов.

    Returns:
        str: Подписанный access-токен.
    """
    await rotate_jwk(TTL_SECONDS)
    token, _ = await sign_token(SUBJECT, SID, not_required={"srl": SUBJECT_ROLE})

    return token


def _authorization(token: str) -> dict[str, str]:
    """Собирает заголовок авторизации с Bearer-токеном.

    Args:
        token (str): Access-токен.

    Returns:
        dict[str, str]: Заголовок `Authorization`.
    """
    return {"Authorization": f"Bearer {token}"}


def _token_jti(token: str) -> str:
    """Возвращает `jti` токена без проверки подписи.

    Args:
        token (str): Подписанный JWT.

    Returns:
        str: Идентификатор токена (`jti`).
    """
    return jwt.decode(token, options={"verify_signature": False})["jti"]


async def test_logout_revokes_token_and_returns_no_content(
    logout_client: ASGIClient,
    rotate_jwk: RotateJwk,
    sign_token: SignToken,
    redis_double: InMemoryRedis,
) -> None:
    """Выход с действующим токеном.

    Given: клиент с действующим access-токеном,
    When: он завершает сессию,
    Then: приходит 204 без тела, а токен попадает в блэклист до конца срока действия.
    """
    # Дано
    token = await _issue_token(rotate_jwk, sign_token)

    # Когда
    response = await logout_client.post(LOGOUT_PATH, headers=_authorization(token))

    # Тогда
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.body == b""
    assert "content-type" not in response.headers

    key = f"token:access:revoked:{_token_jti(token)}"
    assert redis_double.values[key] == "1"
    assert 0 < redis_double.ttl[key] <= config.security.ACCESS_TOKEN_TTL


async def test_logout_rejects_already_revoked_token(
    logout_client: ASGIClient,
    rotate_jwk: RotateJwk,
    sign_token: SignToken,
) -> None:
    """Повторный выход с тем же токеном.

    Given: токен уже отозван предыдущим выходом,
    When: клиент повторяет выход с этим токеном,
    Then: приходит 403: отозванный токен больше не принимается.
    """
    # Дано
    token = await _issue_token(rotate_jwk, sign_token)
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
    rotate_jwk: RotateJwk,
    private_jwk_repository: FilePrivateJwkRepository,
) -> None:
    """Выход с просроченным токеном.

    Given: срок действия токена уже истёк,
    When: клиент пытается завершить сессию,
    Then: приходит 403: просроченный токен не принимается.
    """
    # Дано
    await rotate_jwk(TTL_SECONDS)
    expired = SignToken(
        AccessTokenConfig(issuer=config.app.NAME, audience=config.app.PROJECT, ttl=-1),
        private_jwk_repository,
    )
    token, _ = await expired(SUBJECT, SID, not_required={"srl": SUBJECT_ROLE})

    # Когда
    response = await logout_client.post(LOGOUT_PATH, headers=_authorization(token))

    # Тогда
    assert response.status_code == status.HTTP_403_FORBIDDEN
