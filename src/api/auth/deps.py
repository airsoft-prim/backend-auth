from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.api._protection import schema
from src.core.configs import config
from src.general.security import PASSWORD_HASHER, AccessTokenClaims
from src.providers.cache import StorageNumber, get_bounded_client
from src.providers.cache.repositories import PublicJWKRepository, RevokedTokensRepository
from src.providers.database import get_session
from src.providers.database.models import User
from src.providers.database.repositories import UserRepository
from src.providers.filesystem import FileSystem
from src.providers.filesystem.repositories import PrivateJWKRepository
from src.services import (
    AuthorizationService,
    JWTDecryptionError,
    JWTDecryptionService,
    JWTEncryptionService,
)
from src.services.token import TokenRevocationService
from src.services.user import UserService


async def get_user_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserService:
    """Предоставляет сервис учётных записей на время запроса.

    Сессия БД живёт вместе с запросом: коммит делает репозиторий при сохранении.

    Args:
        session (AsyncSession): Асинхронная сессия БД.

    Returns:
        UserService: Сервис учётных записей, привязанный к сессии запроса.
    """
    return UserService(UserRepository(session), hasher=PASSWORD_HASHER)


async def get_encryption_service() -> JWTEncryptionService:
    """Предоставляет сервис выпуска JWT токенов для открытия новой сессии пользователя.

    Returns:
        JWTEncryptionService: Сервис выпуска JWT токенов.
    """

    private_key_repo = PrivateJWKRepository(FileSystem(config.security.KEY_STORE_DIRECTORY))

    return JWTEncryptionService(private_key_repository=private_key_repo)


async def get_decryption_service(
    client: Annotated[Redis, Depends(get_bounded_client(StorageNumber.KEYS.value))],
) -> JWTDecryptionService:
    """Предоставляет сервис проверки JWT токенов на время запроса.

    Args:
        client (Redis): Клиент Redis с опубликованными публичными JWK.

    Returns:
        JWTDecryptionService: Сервис проверки JWT токенов.
    """
    return JWTDecryptionService(PublicJWKRepository(client))


async def get_token_revocation_service(
    client: Annotated[Redis, Depends(get_bounded_client(StorageNumber.TOKENS.value))],
) -> TokenRevocationService:
    """Предоставляет сервис отзыва токенов на время запроса.

    Args:
        client (Redis): Клиент Redis с отозванными токенами.

    Returns:
        TokenRevocationService: Сервис отзыва токенов.
    """
    return TokenRevocationService(RevokedTokensRepository(client))


async def get_authorization_service(
    decryption_service: Annotated[JWTDecryptionService, Depends(get_decryption_service)],
    revocation_service: Annotated[TokenRevocationService, Depends(get_token_revocation_service)],
) -> AuthorizationService:
    """Предоставляет сервис авторизации запроса на время запроса.

    Args:
        decryption_service (JWTDecryptionService): Сервис проверки JWT токенов.
        revocation_service (TokenRevocationService): Сервис проверки отзыва токенов.

    Returns:
        AuthorizationService: Сервис проверки Bearer-токена и его отзыва.
    """
    return AuthorizationService(decryption_service, revocation_service)


async def get_access_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(schema)],
    authorization_service: Annotated[AuthorizationService, Depends(get_authorization_service)],
) -> AccessTokenClaims:
    """Проверяет Bearer-токен и возвращает его claims.

    Args:
        token (str | None): Токен из заголовка `Authorization`.
        authorization_service (AuthorizationService): Сервис авторизации запроса.

    Raises:
        UserAuthorizationError: Токен не передан.
        JWTDecryptionError: Токен недействителен или уже отозван.

    Returns:
        AccessTokenClaims: Проверенные claims токена.
    """
    token = credentials.credentials if credentials is not None else None

    return await authorization_service.authorize(token)


async def get_current_user(
    claims: Annotated[AccessTokenClaims, Depends(get_access_token)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> User:
    """Возвращает учётную запись владельца проверенного токена.

    Args:
        claims (AccessTokenClaims): Проверенные claims токена.
        user_service (UserService): Сервис учётных записей.

    Raises:
        JWTDecryptionError: В `sub` токена не числовой идентификатор пользователя.
        UserIdentificationError: Учётная запись из `sub` не найдена.

    Returns:
        User: Учётная запись владельца токена.
    """
    try:
        user_id = int(claims["sub"])
    except (TypeError, ValueError) as error:
        msg = "Token subject is invalid."
        raise JWTDecryptionError(msg) from error

    return await user_service.get_account(user_id)
