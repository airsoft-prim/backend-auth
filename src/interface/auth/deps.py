from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.cache import StorageNumber, get_bounded_client
from src.adapters.cache.repositories import (
    RedisPublicJwkRepository,
    RedisRevokedTokensRepository,
)
from src.adapters.crypto.hasher import PASSWORD_HASHER
from src.adapters.database import get_session
from src.adapters.database.repositories import SqlAlchemyUserRepository
from src.adapters.filesystem import FileSystem
from src.adapters.filesystem.repositories import FilePrivateJwkRepository
from src.application.auth import AuthorizationService, UserService
from src.application.token import (
    JWTDecryptionError,
    JWTDecryptionService,
    JWTEncryptionService,
    TokenRevocationService,
)
from src.config import config
from src.domain.entities import AccessTokenClaims, User
from src.interface._protection import schema


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
    return UserService(SqlAlchemyUserRepository(session), hasher=PASSWORD_HASHER)


async def get_encryption_service() -> JWTEncryptionService:
    """Предоставляет сервис выпуска JWT токенов для открытия новой сессии пользователя.

    Returns:
        JWTEncryptionService: Сервис выпуска JWT токенов.
    """
    private_key_repo = FilePrivateJwkRepository(FileSystem(config.security.KEY_STORE_DIRECTORY))

    return JWTEncryptionService(
        private_key_repository=private_key_repo,
        issuer=config.app.NAME,
        audience=config.app.PROJECT,
        ttl=config.security.ACCESS_TOKEN_TTL,
    )


async def get_decryption_service(
    client: Annotated[Redis, Depends(get_bounded_client(StorageNumber.KEYS.value))],
) -> JWTDecryptionService:
    """Предоставляет сервис проверки JWT токенов на время запроса.

    Args:
        client (Redis): Клиент Redis с опубликованными публичными JWK.

    Returns:
        JWTDecryptionService: Сервис проверки JWT токенов.
    """
    return JWTDecryptionService(
        public_key_repository=RedisPublicJwkRepository(client),
        issuer=config.app.NAME,
        audience=config.app.PROJECT,
    )


async def get_token_revocation_service(
    client: Annotated[Redis, Depends(get_bounded_client(StorageNumber.TOKENS.value))],
) -> TokenRevocationService:
    """Предоставляет сервис отзыва токенов на время запроса.

    Args:
        client (Redis): Клиент Redis с отозванными токенами.

    Returns:
        TokenRevocationService: Сервис отзыва токенов.
    """
    return TokenRevocationService(RedisRevokedTokensRepository(client))


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
