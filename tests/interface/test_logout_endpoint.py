"""Тесты HTTP-контракта выхода из системы."""

from fastapi import FastAPI, status
import pytest

from src.adapters.cache.repositories import RedisRevokedTokensRepository, RedisSessionRepository
from src.adapters.filesystem.repositories import FilePrivateJwkRepository
from src.application import EnsureTokenActive, RevokeSession, SignToken, VerifyToken
from src.application.jwk import RotateJwk
from src.config import config
from src.domain.tokens import RefreshTokenClaims, RefreshTokenConfig
from src.interface.auth.deps import (
    get_ensure_token_active,
    get_revoke_session,
    get_verify_refresh_token,
)
from tests.asgi_client import ASGIClient
from tests.doubles import InMemoryRedis

LOGOUT_PATH = "/auth/logout"
SUBJECT = 42
SID = "session-under-test"
TTL_SECONDS = 3600


@pytest.fixture
def logout_client(
    api_app: FastAPI,
    verify_refresh_token: VerifyToken[RefreshTokenClaims],
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
    session_repository: RedisSessionRepository,
) -> ASGIClient:
    """Отдаёт клиент выхода с подменой проверки refresh-токена и хранилища отзыва.

    Args:
        api_app (FastAPI): Приложение под тестом.
        verify_refresh_token (VerifyToken[RefreshTokenClaims]): Use case проверки
            refresh-токенов поверх подмены Redis с опубликованными JWK.
        blacklisted_tokens_repository (RedisRevokedTokensRepository): Репозиторий
            отозванных токенов поверх подмены Redis.

    Returns:
        ASGIClient: Клиент маршрута выхода.
    """
    api_app.dependency_overrides[get_verify_refresh_token] = lambda: verify_refresh_token
    api_app.dependency_overrides[get_ensure_token_active] = lambda: EnsureTokenActive(
        blacklisted_tokens_repository
    )
    api_app.dependency_overrides[get_revoke_session] = lambda: RevokeSession(
        blacklisted_tokens_repository, session_repository
    )

    return ASGIClient(api_app)


async def _issue_token(
    rotate_jwk: RotateJwk,
    sign_refresh_token: SignToken,
) -> str:
    """Публикует ключ и выпускает refresh-токен для проверки выхода.

    Args:
        rotate_jwk (RotateJwk): Use case генерации и публикации ключей.
        sign_refresh_token (SignToken): Use case выпуска refresh-токенов.

    Returns:
        str: Подписанный refresh-токен.
    """
    await rotate_jwk(TTL_SECONDS)
    token, _ = await sign_refresh_token(SUBJECT, SID)

    return token


def _cookie(token: str) -> dict[str, str]:
    """Собирает заголовок cookie с refresh-токеном.

    Args:
        token (str): Refresh-токен.

    Returns:
        dict[str, str]: Заголовок `Cookie`.
    """
    return {"cookie": f"refresh_token={token}"}


async def test_logout_revokes_token_and_returns_no_content(
    logout_client: ASGIClient,
    rotate_jwk: RotateJwk,
    sign_refresh_token: SignToken,
    redis_double: InMemoryRedis,
) -> None:
    """Выход с действующим refresh-токеном.

    Given: клиент с действующим refresh-токеном,
    When: он завершает сессию,
    Then: приходит 204 без тела, а сессия (`sid`) попадает в блэклист до конца срока
    действия refresh-токена.
    """
    # Дано
    token = await _issue_token(rotate_jwk, sign_refresh_token)

    # Когда
    response = await logout_client.post(LOGOUT_PATH, headers=_cookie(token))

    # Тогда
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.body == b""
    assert "content-type" not in response.headers
    assert "refresh_token" in response.headers.get("set-cookie", "")

    key = f"session:revoked:{SID}"
    assert redis_double.values[key] == "1"
    assert 0 < redis_double.ttl[key] <= config.security.REFRESH_TOKEN_TTL


async def test_logout_rejects_already_revoked_token(
    logout_client: ASGIClient,
    rotate_jwk: RotateJwk,
    sign_refresh_token: SignToken,
) -> None:
    """Повторный выход с тем же refresh-токеном.

    Given: refresh-токен уже отозван предыдущим выходом,
    When: клиент повторяет выход с этим токеном,
    Then: приходит 403: отозванный токен больше не принимается.
    """
    # Дано
    token = await _issue_token(rotate_jwk, sign_refresh_token)
    await logout_client.post(LOGOUT_PATH, headers=_cookie(token))

    # Когда
    response = await logout_client.post(LOGOUT_PATH, headers=_cookie(token))

    # Тогда
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.payload == {
        "message": "Authorization failed.",
        "details": "Provided credentials are invalid.",
    }


async def test_logout_requires_refresh_cookie(logout_client: ASGIClient) -> None:
    """Выход без refresh-токена в cookie.

    Given: запрос без cookie с refresh-токеном,
    When: клиент пытается завершить сессию,
    Then: приходит 401: сессию не идентифицировать.
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
    response = await logout_client.post(LOGOUT_PATH, headers=_cookie("not-a-jwt"))

    # Тогда
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.payload["message"] == "Authorization failed."


async def test_logout_rejects_expired_token(
    logout_client: ASGIClient,
    rotate_jwk: RotateJwk,
    private_jwk_repository: FilePrivateJwkRepository,
) -> None:
    """Выход с просроченным refresh-токеном.

    Given: срок действия refresh-токена уже истёк,
    When: клиент пытается завершить сессию,
    Then: приходит 403: просроченный токен не принимается.
    """
    # Дано
    await rotate_jwk(TTL_SECONDS)
    expired = SignToken(
        RefreshTokenConfig(issuer=config.app.NAME, audience=config.app.NAME, ttl=-1),
        private_jwk_repository,
    )
    token, _ = await expired(SUBJECT, SID)

    # Когда
    response = await logout_client.post(LOGOUT_PATH, headers=_cookie(token))

    # Тогда
    assert response.status_code == status.HTTP_403_FORBIDDEN
