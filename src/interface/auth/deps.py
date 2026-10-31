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
from src.application.auth import GetUser, LoginUser, RegisterUser
from src.application.token import (
    Authorize,
    EnsureTokenActive,
    IssueAccessToken,
    RevokeToken,
    VerifyAccessToken,
)
from src.config import config
from src.domain.entities import AccessTokenClaims, User
from src.domain.errors import JWTDecryptionError
from src.interface._protection import schema


async def get_register_user(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RegisterUser:
    """Предоставляет use case регистрации на время запроса.

    Args:
        session (AsyncSession): Асинхронная сессия БД.

    Returns:
        RegisterUser: Use case регистрации, привязанный к сессии запроса.
    """
    return RegisterUser(SqlAlchemyUserRepository(session), hasher=PASSWORD_HASHER)


async def get_login_user(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LoginUser:
    """Предоставляет use case входа на время запроса.

    Args:
        session (AsyncSession): Асинхронная сессия БД.

    Returns:
        LoginUser: Use case входа, привязанный к сессии запроса.
    """
    return LoginUser(SqlAlchemyUserRepository(session), hasher=PASSWORD_HASHER)


async def get_user(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GetUser:
    """Предоставляет use case получения учётной записи на время запроса.

    Args:
        session (AsyncSession): Асинхронная сессия БД.

    Returns:
        GetUser: Use case получения учётной записи по идентификатору.
    """
    return GetUser(SqlAlchemyUserRepository(session))


async def get_issue_access_token() -> IssueAccessToken:
    """Предоставляет use case выпуска access-токена.

    Returns:
        IssueAccessToken: Use case выпуска JWT-токена.
    """
    private_key_repo = FilePrivateJwkRepository(FileSystem(config.security.KEY_STORE_DIRECTORY))

    return IssueAccessToken(
        private_key_repository=private_key_repo,
        issuer=config.app.NAME,
        audience=config.app.PROJECT,
        ttl=config.security.ACCESS_TOKEN_TTL,
    )


async def get_verify_access_token(
    client: Annotated[Redis, Depends(get_bounded_client(StorageNumber.KEYS.value))],
) -> VerifyAccessToken:
    """Предоставляет use case проверки access-токена на время запроса.

    Args:
        client (Redis): Клиент Redis с опубликованными публичными JWK.

    Returns:
        VerifyAccessToken: Use case проверки JWT-токена.
    """
    return VerifyAccessToken(
        public_key_repository=RedisPublicJwkRepository(client),
        issuer=config.app.NAME,
        audience=config.app.PROJECT,
    )


async def get_ensure_token_active(
    client: Annotated[Redis, Depends(get_bounded_client(StorageNumber.TOKENS.value))],
) -> EnsureTokenActive:
    """Предоставляет use case проверки отзыва токена на время запроса.

    Args:
        client (Redis): Клиент Redis с отозванными токенами.

    Returns:
        EnsureTokenActive: Use case проверки, что токен не отозван.
    """
    return EnsureTokenActive(RedisRevokedTokensRepository(client))


async def get_revoke_token(
    client: Annotated[Redis, Depends(get_bounded_client(StorageNumber.TOKENS.value))],
) -> RevokeToken:
    """Предоставляет use case отзыва токена на время запроса.

    Args:
        client (Redis): Клиент Redis с отозванными токенами.

    Returns:
        RevokeToken: Use case отзыва токена.
    """
    return RevokeToken(RedisRevokedTokensRepository(client))


async def get_authorize(
    verify: Annotated[VerifyAccessToken, Depends(get_verify_access_token)],
    ensure_active: Annotated[EnsureTokenActive, Depends(get_ensure_token_active)],
) -> Authorize:
    """Предоставляет use case авторизации запроса на время запроса.

    Args:
        verify (VerifyAccessToken): Use case проверки JWT-токена.
        ensure_active (EnsureTokenActive): Use case проверки отзыва токена.

    Returns:
        Authorize: Use case проверки Bearer-токена и его отзыва.
    """
    return Authorize(verify, ensure_active)


async def get_access_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(schema)],
    authorize: Annotated[Authorize, Depends(get_authorize)],
) -> AccessTokenClaims:
    """Проверяет Bearer-токен и возвращает его claims.

    Args:
        credentials (HTTPAuthorizationCredentials | None): Учётные данные заголовка
            `Authorization`.
        authorize (Authorize): Use case авторизации запроса.

    Raises:
        UserAuthorizationError: Токен не передан.
        JWTDecryptionError: Токен недействителен или уже отозван.

    Returns:
        AccessTokenClaims: Проверенные claims токена.
    """
    token = credentials.credentials if credentials is not None else None

    return await authorize(token)


async def get_current_user(
    claims: Annotated[AccessTokenClaims, Depends(get_access_token)],
    fetch_user: Annotated[GetUser, Depends(get_user)],
) -> User:
    """Возвращает учётную запись владельца проверенного токена.

    Args:
        claims (AccessTokenClaims): Проверенные claims токена.
        fetch_user (GetUser): Use case получения учётной записи по идентификатору.

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

    return await fetch_user(user_id)
