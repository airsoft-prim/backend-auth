"""Тесты HTTP-контракта профиля владельца токена."""

from datetime import UTC, datetime

from fastapi import FastAPI, status
import jwt
import pytest

from src.adapters.cache.repositories import (
    RedisRevokedSessionsRepository,
    RedisRevokedTokensRepository,
)
from src.application import EnsureTokenActive, SignToken, VerifyToken
from src.application.auth import GetUser
from src.application.jwk import RotateJwk
from src.domain.entities import User
from src.domain.enums import TokenType, UserRole
from src.interface.auth.deps import (
    get_ensure_token_active,
    get_user,
    get_verify_access_token,
)
from tests.asgi_client import ASGIClient
from tests.doubles import InMemoryUserRepository, as_user_repository

ME_PATH = "/auth/me"
USER_ID = 42
USERNAME = "stalker_2010"
EMAIL = "user@airsoft-prim.ru"
SUBJECT_ROLE = "user"
SID = "session-under-test"
TTL_SECONDS = 3600
CREATED_AT = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
UPDATED_AT = datetime(2026, 9, 2, 13, 30, tzinfo=UTC)


@pytest.fixture
def user_repository() -> InMemoryUserRepository:
    """Отдаёт пустую подмену репозитория учётных записей.

    Returns:
        InMemoryUserRepository: Хранилище учётных записей в памяти.
    """
    return InMemoryUserRepository()


@pytest.fixture
def me_client(
    api_app: FastAPI,
    user_repository: InMemoryUserRepository,
    verify_token: VerifyToken,
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
    revoked_sessions_repository: RedisRevokedSessionsRepository,
) -> ASGIClient:
    """Отдаёт клиент профиля с подменами БД, проверки токена и хранилища отзыва.

    Args:
        api_app (FastAPI): Приложение под тестом.
        user_repository (InMemoryUserRepository): Подмена репозитория учётных записей.
        verify_token (VerifyToken): Use case проверки токенов поверх
            подмены Redis с опубликованными JWK.
        blacklisted_tokens_repository (RedisRevokedTokensRepository): Репозиторий
            отозванных токенов поверх подмены Redis.
        revoked_sessions_repository (RedisRevokedSessionsRepository): Репозиторий
            отозванных сессий поверх подмены Redis.

    Returns:
        ASGIClient: Клиент маршрута профиля.
    """
    api_app.dependency_overrides[get_user] = lambda: GetUser(as_user_repository(user_repository))
    api_app.dependency_overrides[get_verify_access_token] = lambda: verify_token
    api_app.dependency_overrides[get_ensure_token_active] = lambda: EnsureTokenActive(
        blacklisted_tokens_repository, revoked_sessions_repository
    )

    return ASGIClient(api_app)


def _stored_account(
    *,
    disabled: bool = False,
    role: UserRole = UserRole.MODERATOR,
) -> User:
    """Собирает учётную запись для ответа профиля.

    Args:
        disabled (bool, optional): Признак блокировки. Defaults to False.
        role (UserRole, optional): Системная роль. Defaults to `UserRole.MODERATOR`.

    Returns:
        User: Учётная запись с заполненными Id и метками времени.
    """
    account = User(
        username=USERNAME,
        email=EMAIL,
        pswd_hash="stored-hash",
        system_role=role,
        disabled=disabled,
    )
    account.id = USER_ID
    account.created_at = CREATED_AT
    account.updated_at = UPDATED_AT

    return account


async def _issue_token(
    rotate_jwk: RotateJwk,
    sign_token: SignToken,
    *,
    subject: int | str = USER_ID,
) -> str:
    """Публикует ключ и выпускает access-токен для проверки профиля.

    Args:
        rotate_jwk (RotateJwk): Use case генерации и публикации ключей.
        sign_token (SignToken): Use case выпуска токенов.
        subject (int | str, optional): Идентификатор пользователя в `sub`.
            Defaults to USER_ID.

    Returns:
        str: Подписанный access-токен.
    """
    await rotate_jwk(TTL_SECONDS)
    token, _ = await sign_token(subject, SID, not_required={"srl": SUBJECT_ROLE})

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


async def test_me_returns_owner_profile(
    me_client: ASGIClient,
    user_repository: InMemoryUserRepository,
    rotate_jwk: RotateJwk,
    sign_token: SignToken,
) -> None:
    """Профиль владельца действующего токена.

    Given: действующий токен и учётная запись с этим Id,
    When: владелец запрашивает свой профиль,
    Then: приходит 200 с данными учётной записи без хеша пароля и служебных полей.
    """
    # Дано
    user_repository.users.append(_stored_account())
    token = await _issue_token(rotate_jwk, sign_token)

    # Когда
    response = await me_client.get(ME_PATH, headers=_authorization(token))

    # Тогда
    assert response.status_code == status.HTTP_200_OK

    body = response.payload
    assert set(body) == {"id", "username", "email", "role", "created_at", "updated_at"}
    assert body["id"] == USER_ID
    assert body["username"] == USERNAME
    assert body["email"] == EMAIL
    assert body["role"] == UserRole.MODERATOR.value
    assert datetime.fromisoformat(body["created_at"]) == CREATED_AT
    assert datetime.fromisoformat(body["updated_at"]) == UPDATED_AT
    assert "pswd_hash" not in body
    assert "disabled" not in body


async def test_me_returns_profile_of_blocked_user(
    me_client: ASGIClient,
    user_repository: InMemoryUserRepository,
    rotate_jwk: RotateJwk,
    sign_token: SignToken,
) -> None:
    """Профиль заблокированного владельца токена.

    Given: учётная запись заблокирована, но её токен ещё действует,
    When: владелец запрашивает профиль,
    Then: приходит 200: блокировка закрывает вход, но не отзывает уже выданный токен.
    """
    # Дано
    user_repository.users.append(_stored_account(disabled=True))
    token = await _issue_token(rotate_jwk, sign_token)

    # Когда
    response = await me_client.get(ME_PATH, headers=_authorization(token))

    # Тогда
    assert response.status_code == status.HTTP_200_OK
    assert response.payload["id"] == USER_ID
    assert "disabled" not in response.payload


async def test_me_requires_bearer_token(me_client: ASGIClient) -> None:
    """Профиль без заголовка авторизации.

    Given: запрос без заголовка `Authorization`,
    When: клиент запрашивает профиль,
    Then: приходит 401 с требованием Bearer-аутентификации.
    """
    # Когда
    response = await me_client.get(ME_PATH)

    # Тогда
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.payload == {
        "message": "Authorization failed.",
        "details": "Bearer token is missing.",
    }


async def test_me_rejects_invalid_token(me_client: ASGIClient) -> None:
    """Профиль с невалидным токеном.

    Given: в заголовке передана строка, не являющаяся JWT,
    When: клиент запрашивает профиль,
    Then: приходит 403: токен не проходит проверку.
    """
    # Когда
    response = await me_client.get(ME_PATH, headers=_authorization("not-a-jwt"))

    # Тогда
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.payload["message"] == "Authorization failed."


async def test_me_rejects_revoked_token(
    me_client: ASGIClient,
    user_repository: InMemoryUserRepository,
    rotate_jwk: RotateJwk,
    sign_token: SignToken,
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
) -> None:
    """Профиль с отозванным токеном.

    Given: токен уже отозван выходом,
    When: клиент запрашивает профиль,
    Then: приходит 403: отозванный токен больше не принимается.
    """
    # Дано
    user_repository.users.append(_stored_account())
    token = await _issue_token(rotate_jwk, sign_token)
    await blacklisted_tokens_repository.store(
        token_type=TokenType.ACCESS,
        token_id=_token_jti(token),
        ttl=TTL_SECONDS,
    )

    # Когда
    response = await me_client.get(ME_PATH, headers=_authorization(token))

    # Тогда
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_me_rejects_unknown_user(
    me_client: ASGIClient,
    rotate_jwk: RotateJwk,
    sign_token: SignToken,
) -> None:
    """Профиль токена, чья учётная запись не найдена.

    Given: токен подписан, но учётной записи с его `sub` нет,
    When: клиент запрашивает профиль,
    Then: приходит 401: владельца токена идентифицировать нельзя.
    """
    # Дано
    token = await _issue_token(rotate_jwk, sign_token)

    # Когда
    response = await me_client.get(ME_PATH, headers=_authorization(token))

    # Тогда
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers["www-authenticate"] == "Bearer"


async def test_me_rejects_non_numeric_subject(
    me_client: ASGIClient,
    rotate_jwk: RotateJwk,
    sign_token: SignToken,
) -> None:
    """Профиль токена с нечисловым субъектом.

    Given: в `sub` токена лежит не числовой идентификатор,
    When: клиент запрашивает профиль,
    Then: приходит 403: токен не позволяет выбрать учётную запись.
    """
    # Дано
    token = await _issue_token(rotate_jwk, sign_token, subject="not-a-number")

    # Когда
    response = await me_client.get(ME_PATH, headers=_authorization(token))

    # Тогда
    assert response.status_code == status.HTTP_403_FORBIDDEN
