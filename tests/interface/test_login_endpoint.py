"""Тесты HTTP-контракта входа в систему."""

from fastapi import FastAPI, status
import jwt
import pytest

from src.adapters.cache.repositories import RedisSessionRepository
from src.adapters.crypto.hasher import PASSWORD_HASHER
from src.application import CreateSession, SignToken
from src.application.auth import OpenUserSession
from src.application.jwk import RotateJwk
from src.config import config
from src.domain.entities import User
from src.interface.auth.deps import (
    get_open_user_session,
)
from tests.asgi_client import ASGIClient
from tests.doubles import InMemoryUserRepository, as_user_repository

LOGIN_PATH = "/auth/login"
USER_ID = 42
USERNAME = "stalker_2010"
PASSWORD = "Str0ng!Pass"  # noqa: S105
ROLE = "moderator"
TTL_SECONDS = 3600


@pytest.fixture
def login_client(
    api_app: FastAPI,
    sign_refresh_token: SignToken,
    session_repository: RedisSessionRepository,
) -> ASGIClient:
    """Отдаёт клиент входа с подменами сервиса учётных записей, сессий и подписи токенов.

    Args:
        api_app (FastAPI): Приложение под тестом.
        sign_refresh_token (SignToken): Use case подписи `refresh`-токенов.
        session_repository (RedisSessionRepository): Репозиторий сессий поверх подмены `Redis`.

    Returns:
        ASGIClient: Клиент маршрута входа.
    """
    users = InMemoryUserRepository()
    user = User(
        username=USERNAME, email="user@example.org", pswd_hash=PASSWORD_HASHER.hash(PASSWORD)
    )
    user.id = USER_ID
    users.users.append(user)
    api_app.dependency_overrides[get_open_user_session] = lambda: OpenUserSession(
        as_user_repository(users),
        PASSWORD_HASHER,
        CreateSession(
            session_repository,
            config.security.REFRESH_TOKEN_TTL,
            config.security.MAX_ACTIVE_SESSIONS,
        ),
        sign_refresh_token,
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
    """Вход открывает сессию и кладёт `refresh`-токен в cookie.

    Given: сгенерирован ключ подписи, а логин и пароль верны, When: гость входит в систему, Then:
    приходит `204` без тела, а `refresh`-токен — в HTTP-only cookie без роли; `access`-токен вход
    не выдаёт.

    Args:
        login_client (ASGIClient): ASGI-клиент входа с тестовыми зависимостями.
        rotate_jwk (RotateJwk): Сценарий ротации ключей с тестовыми хранилищами.
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
