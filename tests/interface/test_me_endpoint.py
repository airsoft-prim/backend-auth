"""Тесты HTTP-контракта профиля владельца токена."""

from datetime import UTC, datetime

from fastapi import FastAPI, status
import pytest

from src.api.auth.deps import get_decryption_service, get_token_revocation_service, get_user_service
from src.general.enums import TokenType, UserRole
from src.general.security import PASSWORD_HASHER
from src.providers.cache.repositories import RevokedTokensRepository
from src.providers.database.models import User
from src.services import JWTDecryptionService, JWTEncryptionService, TokenRevocationService
from src.services.jwk import JWKGenerationService
from src.services.user import UserService
from tests.asgi_client import ASGIClient
from tests.doubles import InMemoryUserRepository, as_user_repository

ME_PATH = "/auth/me"
USER_ID = 42
USERNAME = "stalker_2010"
EMAIL = "user@airsoft-prim.ru"
TOKEN_ID = "me-token-under-test"  # noqa: S105
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
    decryption_service: JWTDecryptionService,
    blacklisted_tokens_repository: RevokedTokensRepository,
) -> ASGIClient:
    """Отдаёт клиент профиля с подменами БД, проверки токена и хранилища отзыва.

    Args:
        api_app (FastAPI): Приложение под тестом.
        user_repository (InMemoryUserRepository): Подмена репозитория учётных записей.
        decryption_service (JWTDecryptionService): Сервис проверки токенов поверх
            подмены Redis с опубликованными JWK.
        blacklisted_tokens_repository (RevokedTokensRepository): Репозиторий
            отозванных токенов поверх подмены Redis.

    Returns:
        ASGIClient: Клиент маршрута профиля.
    """
    user_service = UserService(
        user_repository=as_user_repository(user_repository),
        hasher=PASSWORD_HASHER,
    )

    api_app.dependency_overrides[get_user_service] = lambda: user_service
    api_app.dependency_overrides[get_decryption_service] = lambda: decryption_service
    api_app.dependency_overrides[get_token_revocation_service] = lambda: TokenRevocationService(
        blacklisted_tokens_repository
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
    jwk_service: JWKGenerationService,
    encryption_service: JWTEncryptionService,
    *,
    subject: int | str = USER_ID,
    ttl: int = TTL_SECONDS,
) -> str:
    """Публикует ключ и выпускает access-токен для проверки профиля.

    Args:
        jwk_service (JWKGenerationService): Сервис генерации и публикации ключей.
        encryption_service (JWTEncryptionService): Сервис выпуска токенов.
        subject (int | str, optional): Идентификатор пользователя в `sub`.
            Defaults to USER_ID.
        ttl (int, optional): Срок жизни токена в секундах. Defaults to TTL_SECONDS.

    Returns:
        str: Подписанный access-токен.
    """
    await jwk_service.generate_jwk(TTL_SECONDS)
    token, _ = await encryption_service.encrypt(subject, token_id=TOKEN_ID, ttl=ttl)

    return token


def _authorization(token: str) -> dict[str, str]:
    """Собирает заголовок авторизации с Bearer-токеном.

    Args:
        token (str): Access-токен.

    Returns:
        dict[str, str]: Заголовок `Authorization`.
    """
    return {"Authorization": f"Bearer {token}"}


async def test_me_returns_owner_profile(
    me_client: ASGIClient,
    user_repository: InMemoryUserRepository,
    jwk_service: JWKGenerationService,
    encryption_service: JWTEncryptionService,
) -> None:
    """Профиль владельца действующего токена.

    Given: действующий токен и учётная запись с этим Id,
    When: владелец запрашивает свой профиль,
    Then: приходит 200 с данными учётной записи без хеша пароля и служебных полей.
    """
    # Дано
    user_repository.users.append(_stored_account())
    token = await _issue_token(jwk_service, encryption_service)

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
    jwk_service: JWKGenerationService,
    encryption_service: JWTEncryptionService,
) -> None:
    """Профиль заблокированного владельца токена.

    Given: учётная запись заблокирована, но её токен ещё действует,
    When: владелец запрашивает профиль,
    Then: приходит 200: блокировка закрывает вход, но не отзывает уже выданный токен.
    """
    # Дано
    user_repository.users.append(_stored_account(disabled=True))
    token = await _issue_token(jwk_service, encryption_service)

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
    jwk_service: JWKGenerationService,
    encryption_service: JWTEncryptionService,
    blacklisted_tokens_repository: RevokedTokensRepository,
) -> None:
    """Профиль с отозванным токеном.

    Given: токен уже отозван выходом,
    When: клиент запрашивает профиль,
    Then: приходит 403: отозванный токен больше не принимается.
    """
    # Дано
    user_repository.users.append(_stored_account())
    token = await _issue_token(jwk_service, encryption_service)
    await blacklisted_tokens_repository.store(
        token_type=TokenType.ACCESS,
        token_id=TOKEN_ID,
        ttl=TTL_SECONDS,
    )

    # Когда
    response = await me_client.get(ME_PATH, headers=_authorization(token))

    # Тогда
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_me_rejects_unknown_user(
    me_client: ASGIClient,
    jwk_service: JWKGenerationService,
    encryption_service: JWTEncryptionService,
) -> None:
    """Профиль токена, чья учётная запись не найдена.

    Given: токен подписан, но учётной записи с его `sub` нет,
    When: клиент запрашивает профиль,
    Then: приходит 401: владельца токена идентифицировать нельзя.
    """
    # Дано
    token = await _issue_token(jwk_service, encryption_service)

    # Когда
    response = await me_client.get(ME_PATH, headers=_authorization(token))

    # Тогда
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers["www-authenticate"] == "Bearer"


async def test_me_rejects_non_numeric_subject(
    me_client: ASGIClient,
    jwk_service: JWKGenerationService,
    encryption_service: JWTEncryptionService,
) -> None:
    """Профиль токена с нечисловым субъектом.

    Given: в `sub` токена лежит не числовой идентификатор,
    When: клиент запрашивает профиль,
    Then: приходит 403: токен не позволяет выбрать учётную запись.
    """
    # Дано
    token = await _issue_token(jwk_service, encryption_service, subject="not-a-number")

    # Когда
    response = await me_client.get(ME_PATH, headers=_authorization(token))

    # Тогда
    assert response.status_code == status.HTTP_403_FORBIDDEN
