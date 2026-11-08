"""Тесты HTTP-контракта обновления `access`-токена."""

from datetime import UTC, datetime, timedelta

from fastapi import FastAPI, status
import jwt
import pytest

from src.adapters.cache.repositories import (
    RedisRevokedSessionsRepository,
    RedisRevokedTokensRepository,
    RedisSessionRepository,
)
from src.application import (
    RevokeSession,
    RotateRefreshToken,
    SignToken,
    VerifyToken,
)
from src.application.auth import GetUser
from src.application.jwk import RotateJwk
from src.application.session import RequireActiveSession
from src.config import config
from src.domain.entities import Session, User
from src.domain.enums import UserRole
from src.domain.tokens import RefreshTokenClaims
from src.interface.auth.deps import (
    get_require_active_session,
    get_rotate_refresh_token,
    get_sign_access_token,
    get_sign_refresh_token,
    get_user,
    get_verify_refresh_token,
)
from tests.asgi_client import ASGIClient
from tests.doubles import InMemoryRedis, InMemoryUserRepository, as_user_repository

REFRESH_PATH = "/auth/refresh"
USER_ID = 42
USERNAME = "stalker_2010"
EMAIL = "user@airsoft-prim.ru"
ROLE = UserRole.MODERATOR
SID = "session-under-test"
TTL_SECONDS = 3600


@pytest.fixture
def user_repository() -> InMemoryUserRepository:
    """Отдаёт подмену репозитория учётных записей с владельцем токена.

    Returns:
        InMemoryUserRepository: Хранилище учётных записей в памяти.
    """
    repository = InMemoryUserRepository()
    account = User(username=USERNAME, email=EMAIL, pswd_hash="stored-hash", system_role=ROLE)
    account.id = USER_ID
    repository.users.append(account)

    return repository


@pytest.fixture
async def refresh_client(  # noqa: PLR0913, PLR0917
    api_app: FastAPI,
    verify_refresh_token: VerifyToken[RefreshTokenClaims],
    sign_token: SignToken,
    sign_refresh_token: SignToken,
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
    revoked_sessions_repository: RedisRevokedSessionsRepository,
    session_repository: RedisSessionRepository,
    user_repository: InMemoryUserRepository,
) -> ASGIClient:
    """Отдаёт клиент обновления с подменами проверки, отзыва, сессий и подписи токенов.

    Args:
        api_app (FastAPI): Приложение под тестом.
        verify_refresh_token (VerifyToken[RefreshTokenClaims]): Use case проверки `refresh`-
            токенов.
        sign_token (SignToken): Use case подписи `access`-токенов.
        sign_refresh_token (SignToken): Use case подписи `refresh`-токенов.
        blacklisted_tokens_repository (RedisRevokedTokensRepository): Репозиторий отозванных
            токенов поверх подмены `Redis`.
        revoked_sessions_repository (RedisRevokedSessionsRepository): Репозиторий отозванных сессий
            поверх подмены `Redis`.
        session_repository (RedisSessionRepository): Репозиторий сессий поверх подмены `Redis`.
        user_repository (InMemoryUserRepository): Подмена репозитория учётных записей.

    Returns:
        ASGIClient: Клиент маршрута обновления.
    """
    api_app.dependency_overrides[get_verify_refresh_token] = lambda: verify_refresh_token
    api_app.dependency_overrides[get_require_active_session] = lambda: RequireActiveSession(
        session_repository
    )
    now = datetime.now(UTC)
    await session_repository.save(
        Session(id=SID, user_id=USER_ID, created_at=now, expires_at=now + timedelta(hours=1))
    )
    api_app.dependency_overrides[get_sign_access_token] = lambda: sign_token
    api_app.dependency_overrides[get_sign_refresh_token] = lambda: sign_refresh_token
    api_app.dependency_overrides[get_rotate_refresh_token] = lambda: RotateRefreshToken(
        session_repository,
        RevokeSession(revoked_sessions_repository, session_repository),
        blacklisted_tokens_repository,
        revoked_sessions_repository,
        config.security.REFRESH_TOKEN_TTL,
    )
    api_app.dependency_overrides[get_user] = lambda: GetUser(as_user_repository(user_repository))

    return ASGIClient(api_app)


async def _issue_refresh_token(
    rotate_jwk: RotateJwk,
    sign_refresh_token: SignToken,
) -> str:
    """Публикует ключ и выпускает `refresh`-токен для обновления.

    Args:
        rotate_jwk (RotateJwk): Use case генерации и публикации ключей.
        sign_refresh_token (SignToken): Use case подписи `refresh`-токенов.

    Returns:
        str: Подписанный `refresh`-токен.
    """
    await rotate_jwk(TTL_SECONDS)
    token, _ = await sign_refresh_token(USER_ID, SID)

    return token


def _cookie(token: str) -> dict[str, str]:
    """Собирает заголовок cookie с `refresh`-токеном.

    Args:
        token (str): Refresh-токен.

    Returns:
        dict[str, str]: Заголовок `Cookie`.
    """
    return {"cookie": f"refresh_token={token}"}


def _payload(token: str) -> dict[str, object]:
    """Возвращает `claims` токена без проверки подписи.

    Args:
        token (str): Подписанный JWT.

    Returns:
        dict[str, object]: Claims токена.
    """
    return jwt.decode(token, options={"verify_signature": False})


async def test_refresh_returns_new_access_token(
    refresh_client: ASGIClient,
    rotate_jwk: RotateJwk,
    sign_refresh_token: SignToken,
) -> None:
    """Обновление `access`-токена по `refresh`-токену.

    Given: действующий `refresh`-токен в cookie, When: клиент запрашивает новый `access`-токен,
    Then: приходит `200` с новым `access`-токеном той же сессии и ролью из БД.

    Args:
        refresh_client (ASGIClient): ASGI-клиент обновления токенов с тестовыми зависимостями.
        rotate_jwk (RotateJwk): Сценарий ротации ключей с тестовыми хранилищами.
        sign_refresh_token (SignToken): Сценарий подписи `refresh`-токена ключом тестового
            хранилища.
    """
    # Дано
    token = await _issue_refresh_token(rotate_jwk, sign_refresh_token)

    # Когда
    response = await refresh_client.post(REFRESH_PATH, headers=_cookie(token))

    # Тогда
    assert response.status_code == status.HTTP_200_OK

    body = response.payload
    assert body["token_type"] == "Bearer"  # noqa: S105
    assert body["expires_in"] == config.security.ACCESS_TOKEN_TTL

    claims = _payload(body["access_token"])
    assert claims["sub"] == str(USER_ID)
    assert claims["sid"] == SID
    assert claims["srl"] == ROLE.value

    set_cookie = response.headers["set-cookie"]
    assert "refresh_token=" in set_cookie


async def test_refresh_rotates_refresh_token(
    refresh_client: ASGIClient,
    rotate_jwk: RotateJwk,
    sign_refresh_token: SignToken,
) -> None:
    """Ротация `refresh`-токена.

    Given: действующий `refresh`-токен в cookie, When: клиент обновляет `access`-токен, Then:
    старый `refresh`-токен отзывается и повторное обновление с ним отклоняется.

    Args:
        refresh_client (ASGIClient): ASGI-клиент обновления токенов с тестовыми зависимостями.
        rotate_jwk (RotateJwk): Сценарий ротации ключей с тестовыми хранилищами.
        sign_refresh_token (SignToken): Сценарий подписи `refresh`-токена ключом тестового
            хранилища.
    """
    # Дано
    token = await _issue_refresh_token(rotate_jwk, sign_refresh_token)

    # Когда
    response = await refresh_client.post(REFRESH_PATH, headers=_cookie(token))

    # Тогда
    assert response.status_code == status.HTTP_200_OK

    response = await refresh_client.post(REFRESH_PATH, headers=_cookie(token))
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_refresh_reuse_revokes_session(
    refresh_client: ASGIClient,
    rotate_jwk: RotateJwk,
    sign_refresh_token: SignToken,
    redis_double: InMemoryRedis,
) -> None:
    """Повторное использование `refresh`-токена отзывает сессию.

    Given: `refresh`-токен уже ротирован один раз, When: тот же токен предъявляется повторно, Then:
    приходит `403`, а сессия (`sid`) помечается отозванной.

    Args:
        refresh_client (ASGIClient): ASGI-клиент обновления токенов с тестовыми зависимостями.
        rotate_jwk (RotateJwk): Сценарий ротации ключей с тестовыми хранилищами.
        sign_refresh_token (SignToken): Сценарий подписи `refresh`-токена ключом тестового
            хранилища.
        redis_double (InMemoryRedis): Подмена `Redis` с хранилищем значений и TTL в памяти.
    """
    # Дано
    token = await _issue_refresh_token(rotate_jwk, sign_refresh_token)
    await refresh_client.post(REFRESH_PATH, headers=_cookie(token))

    # Когда
    response = await refresh_client.post(REFRESH_PATH, headers=_cookie(token))

    # Тогда
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert redis_double.values[f"session:revoked:{SID}"] == "1"


async def test_refresh_requires_refresh_cookie(refresh_client: ASGIClient) -> None:
    """Обновление без `refresh`-токена в cookie.

    Given: запрос без cookie с `refresh`-токеном, When: клиент запрашивает новый `access`-токен,
    Then: приходит `401`: сессию не идентифицировать.

    Args:
        refresh_client (ASGIClient): ASGI-клиент обновления токенов с тестовыми зависимостями.
    """
    # Когда
    response = await refresh_client.post(REFRESH_PATH)

    # Тогда
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_refresh_rejects_invalid_token(refresh_client: ASGIClient) -> None:
    """Обновление с невалидным `refresh`-токеном.

    Given: в cookie передана строка, не являющаяся JWT, When: клиент запрашивает новый `access`-
    токен, Then: приходит `403`: токен не проходит проверку.

    Args:
        refresh_client (ASGIClient): ASGI-клиент обновления токенов с тестовыми зависимостями.
    """
    # Когда
    response = await refresh_client.post(REFRESH_PATH, headers=_cookie("not-a-jwt"))

    # Тогда
    assert response.status_code == status.HTTP_403_FORBIDDEN
