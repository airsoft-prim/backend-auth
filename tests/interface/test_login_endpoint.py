"""Тесты HTTP-контракта входа в систему."""

from fastapi import FastAPI, status
import jwt
import pytest

from src.adapters.cache.repositories import RedisSessionRepository
from src.application import CreateSession, SignToken
from src.application.jwk import RotateJwk
from src.config import config
from src.interface.auth.deps import (
    get_create_session,
    get_login_user,
    get_sign_refresh_token,
)
from tests.asgi_client import ASGIClient

LOGIN_PATH = "/auth/login"
USER_ID = 42
USERNAME = "stalker_2010"
PASSWORD = "Str0ng!Pass"  # noqa: S105
ROLE = "moderator"
TTL_SECONDS = 3600


class StubLoginService:
    """Подмена use case входа: возвращает заданные идентификатор и роль."""

    async def __call__(self, _username: str, _password: str) -> tuple[int, str]:
        """Возвращает идентификатор и роль, не проверяя учётные данные.

        Args:
            _username (str): Логин (не используется).
            _password (str): Пароль (не используется).

        Returns:
            tuple[int, str]: Идентификатор пользователя и его системная роль.
        """
        return USER_ID, ROLE


@pytest.fixture
def login_client(
    api_app: FastAPI,
    sign_refresh_token: SignToken,
    session_repository: RedisSessionRepository,
) -> ASGIClient:
    """Отдаёт клиент входа с подменами сервиса учётных записей, сессий и подписи токенов.

    Args:
        api_app (FastAPI): Приложение под тестом.
        sign_refresh_token (SignToken): Use case подписи refresh-токенов.
        session_repository (RedisSessionRepository): Репозиторий сессий поверх подмены
            Redis.

    Returns:
        ASGIClient: Клиент маршрута входа.
    """
    api_app.dependency_overrides[get_login_user] = StubLoginService
    api_app.dependency_overrides[get_sign_refresh_token] = lambda: sign_refresh_token
    api_app.dependency_overrides[get_create_session] = lambda: CreateSession(
        session_repository,
        config.security.REFRESH_TOKEN_TTL,
        config.security.MAX_ACTIVE_SESSIONS,
    )

    return ASGIClient(api_app)


def _body() -> dict[str, str]:
    """Собирает тело запроса на вход.

    Returns:
        dict[str, str]: Логин и пароль.
    """
    return {"username": USERNAME, "password": PASSWORD}


async def test_login_opens_session_and_sets_refresh_cookie(
    login_client: ASGIClient,
    rotate_jwk: RotateJwk,
) -> None:
    """Вход открывает сессию и кладёт refresh-токен в cookie.

    Given: сгенерирован ключ подписи, а логин и пароль верны,
    When: гость входит в систему,
    Then: приходит 204 без тела, а refresh-токен — в HTTP-only cookie без роли; access-токен
    вход не выдаёт.
    """
    # Дано
    await rotate_jwk(TTL_SECONDS)

    # Когда
    response = await login_client.post(LOGIN_PATH, payload=_body())

    # Тогда
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.body == b""

    set_cookie = response.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    if config.app.DEBUG:
        assert "Secure" not in set_cookie
    else:
        assert "Secure" in set_cookie

    refresh_token = set_cookie.split("refresh_token=", 1)[1].split(";", 1)[0]
    refresh_claims = jwt.decode(refresh_token, options={"verify_signature": False})
    assert refresh_claims["sub"] == str(USER_ID)
    assert refresh_claims["sid"]
    assert "srl" not in refresh_claims
