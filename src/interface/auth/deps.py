from typing import Annotated

from fastapi import Cookie, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.cache import StorageNumber, get_bounded_client
from src.adapters.cache.repositories import (
    RedisPublicJwkRepository,
    RedisRevokedSessionsRepository,
    RedisRevokedTokensRepository,
    RedisSessionRepository,
)
from src.adapters.crypto.hasher import PASSWORD_HASHER
from src.adapters.database import get_session
from src.adapters.database.repositories import SqlAlchemyUserRepository
from src.adapters.filesystem import FileSystem
from src.adapters.filesystem.repositories import FilePrivateJwkRepository
from src.application.auth import GetUser, OpenUserSession, RefreshUserSession, RegisterUser
from src.application.session import CreateSession, RequireActiveSession
from src.application.token import (
    Authorize,
    EnsureTokenActive,
    IssueTokenPair,
    RevokeSession,
    RotateRefreshToken,
    SignToken,
    VerifyToken,
)
from src.config import config
from src.domain.entities import User
from src.domain.enums import TokenType
from src.domain.errors import JWTDecryptionError, UserAuthorizationError
from src.domain.tokens import (
    AccessTokenConfig,
    RefreshTokenClaims,
    RefreshTokenConfig,
)


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


def _access_token_config() -> AccessTokenConfig:
    """Собирает конфигурацию `access`-токена из настроек приложения.

    Returns:
        AccessTokenConfig: Конфигурация `access`-токена.
    """
    return AccessTokenConfig(
        issuer=config.app.NAME,
        audience=config.app.PROJECT,
        ttl=config.security.ACCESS_TOKEN_TTL,
    )


def _refresh_token_config() -> RefreshTokenConfig:
    """Собирает конфигурацию `refresh`-токена из настроек приложения.

    Returns:
        RefreshTokenConfig: Конфигурация `refresh`-токена.
    """
    return RefreshTokenConfig(
        issuer=config.app.NAME,
        audience=config.app.NAME,
        ttl=config.security.REFRESH_TOKEN_TTL,
    )


async def get_sign_access_token() -> SignToken:
    """Предоставляет use case подписи `access`-токена.

    Returns:
        SignToken: Use case подписи JWT-токена.
    """
    private_key_repo = FilePrivateJwkRepository(FileSystem(config.security.KEY_STORE_DIRECTORY))

    return SignToken(_access_token_config(), private_key_repo)


async def get_sign_refresh_token() -> SignToken:
    """Предоставляет use case подписи `refresh`-токена.

    Returns:
        SignToken: Use case подписи JWT-токена.
    """
    private_key_repo = FilePrivateJwkRepository(FileSystem(config.security.KEY_STORE_DIRECTORY))

    return SignToken(_refresh_token_config(), private_key_repo)


async def get_issue_token_pair(
    access: Annotated[SignToken, Depends(get_sign_access_token)],
    refresh: Annotated[SignToken, Depends(get_sign_refresh_token)],
) -> IssueTokenPair:
    """Предоставляет use case выпуска пары токенов на время запроса.

    Args:
        access (SignToken): Use case подписи `access`-токена.
        refresh (SignToken): Use case подписи `refresh`-токена.

    Returns:
        IssueTokenPair: Use case выпуска `access`- и `refresh`-токенов.
    """
    return IssueTokenPair(access, refresh)


async def get_verify_refresh_token(
    client: Annotated[Redis, Depends(get_bounded_client(StorageNumber.KEYS.value))],
) -> VerifyToken[RefreshTokenClaims]:
    """Предоставляет use case проверки `refresh`-токена на время запроса.

    Args:
        client (Redis): Клиент `Redis` с опубликованными публичными JWK.

    Returns:
        VerifyToken[RefreshTokenClaims]: Use case проверки JWT-токена.
    """
    return VerifyToken(_refresh_token_config(), RedisPublicJwkRepository(client))


async def get_ensure_token_active(
    client: Annotated[Redis, Depends(get_bounded_client(StorageNumber.TOKENS.value))],
) -> EnsureTokenActive:
    """Предоставляет use case проверки отзыва токена на время запроса.

    Args:
        client (Redis): Клиент `Redis` с отозванными токенами и сессиями.

    Returns:
        EnsureTokenActive: Use case проверки, что токен не отозван.
    """
    return EnsureTokenActive(
        RedisRevokedTokensRepository(client),
        RedisRevokedSessionsRepository(client),
    )


async def get_revoke_session(
    tokens_client: Annotated[Redis, Depends(get_bounded_client(StorageNumber.TOKENS.value))],
    sessions_client: Annotated[Redis, Depends(get_bounded_client(StorageNumber.SESSIONS.value))],
) -> RevokeSession:
    """Предоставляет use case отзыва сессии на время запроса.

    Args:
        tokens_client (Redis): Клиент `Redis` с отозванными сессиями.
        sessions_client (Redis): Клиент `Redis` с сессиями пользователей.

    Returns:
        RevokeSession: Use case отзыва сессии.
    """
    return RevokeSession(
        RedisRevokedSessionsRepository(tokens_client),
        RedisSessionRepository(sessions_client),
    )


async def get_create_session(
    client: Annotated[Redis, Depends(get_bounded_client(StorageNumber.SESSIONS.value))],
) -> CreateSession:
    """Предоставляет use case создания сессии на время запроса.

    Args:
        client (Redis): Клиент `Redis` с сессиями пользователей.

    Returns:
        CreateSession: Use case создания сессии с лимитом активных сессий.
    """
    return CreateSession(
        RedisSessionRepository(client),
        config.security.REFRESH_TOKEN_TTL,
        config.security.MAX_ACTIVE_SESSIONS,
    )


async def get_rotate_refresh_token(
    revoke_session: Annotated[RevokeSession, Depends(get_revoke_session)],
    tokens_client: Annotated[Redis, Depends(get_bounded_client(StorageNumber.TOKENS.value))],
    sessions_client: Annotated[Redis, Depends(get_bounded_client(StorageNumber.SESSIONS.value))],
) -> RotateRefreshToken:
    """Предоставляет use case ротации `refresh`-токена на время запроса.

    Args:
        revoke_session (RevokeSession): Use case отзыва сессии при краже.
        tokens_client (Redis): Клиент `Redis` с отозванными токенами и сессиями.
        sessions_client (Redis): Клиент `Redis` с сессиями пользователей.

    Returns:
        RotateRefreshToken: Use case ротации `refresh`-токена.
    """
    return RotateRefreshToken(
        RedisSessionRepository(sessions_client),
        revoke_session,
        RedisRevokedTokensRepository(tokens_client),
        RedisRevokedSessionsRepository(tokens_client),
        config.security.REFRESH_TOKEN_TTL,
    )


async def get_authorize_refresh(
    verify: Annotated[VerifyToken[RefreshTokenClaims], Depends(get_verify_refresh_token)],
    ensure_active: Annotated[EnsureTokenActive, Depends(get_ensure_token_active)],
) -> Authorize[RefreshTokenClaims]:
    """Предоставляет use case авторизации по `refresh`-токену на время запроса.

    Args:
        verify (VerifyToken[RefreshTokenClaims]): Use case проверки `refresh`-токена.
        ensure_active (EnsureTokenActive): Use case проверки отзыва токена.

    Returns:
        Authorize[RefreshTokenClaims]: Use case проверки Bearer-токена и его отзыва.
    """
    return Authorize(verify, ensure_active, TokenType.REFRESH)


async def get_require_active_session(
    client: Annotated[Redis, Depends(get_bounded_client(StorageNumber.SESSIONS.value))],
) -> RequireActiveSession:
    """Предоставляет проверку действующей сессии.

    Args:
        client (Redis): Клиент хранилища сессий.

    Returns:
        RequireActiveSession: Проверка принадлежности токена активной сессии.
    """
    return RequireActiveSession(RedisSessionRepository(client))


async def get_refresh_token(
    authorize: Annotated[Authorize[RefreshTokenClaims], Depends(get_authorize_refresh)],
    active_session: Annotated[RequireActiveSession, Depends(get_require_active_session)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> RefreshTokenClaims:
    """Проверяет `refresh`-токен из cookie и возвращает его `claims`.

    Args:
        authorize (Authorize[RefreshTokenClaims]): Use case авторизации по `refresh`-токену.
        active_session (RequireActiveSession): Проверка состояния и владельца сессии.
        refresh_token (str | None): Refresh-токен из HTTP-only cookie.

    Returns:
        RefreshTokenClaims: Проверенные `claims` `refresh`-токена.
    """
    claims = await authorize(refresh_token)
    await active_session(claims)
    return claims


async def get_refresh_claims(
    verify: Annotated[VerifyToken[RefreshTokenClaims], Depends(get_verify_refresh_token)],
    active_session: Annotated[RequireActiveSession, Depends(get_require_active_session)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> RefreshTokenClaims:
    """Проверяет `refresh`-токен из cookie без проверки отзыва.

    Отзыв сессии и обнаружение повторного использования выполняет use case ротации: ему нужен
    предъявленный токен, чтобы отозвать сессию целиком при краже.

    Args:
        verify (VerifyToken[RefreshTokenClaims]): Use case проверки `refresh`-токена.
        active_session (RequireActiveSession): Проверка состояния и владельца сессии.
        refresh_token (str | None): Refresh-токен из HTTP-only cookie.

    Returns:
        RefreshTokenClaims: Проверенные `claims` `refresh`-токена.

    Raises:
        UserAuthorizationError: Refresh-токен не передан.
    """
    if refresh_token is None:
        msg = "Bearer token is missing."
        raise UserAuthorizationError(msg)

    claims = await verify(refresh_token)
    await active_session(claims)
    return claims


async def get_current_user(
    claims: Annotated[RefreshTokenClaims, Depends(get_refresh_token)],
    fetch_user: Annotated[GetUser, Depends(get_user)],
) -> User:
    """Возвращает учётную запись владельца проверенного токена.

    Args:
        claims (RefreshTokenClaims): Проверенные `claims` токена.
        fetch_user (GetUser): Use case получения учётной записи по идентификатору.

    Returns:
        User: Учётная запись владельца токена.

    Raises:
        JWTDecryptionError: В `sub` токена не числовой идентификатор пользователя.
    """
    try:
        user_id = int(claims["sub"])

    except (TypeError, ValueError) as error:
        msg = "Token subject is invalid."
        raise JWTDecryptionError(msg) from error

    return await fetch_user(user_id)


async def get_open_user_session(
    db: Annotated[AsyncSession, Depends(get_session)],
    sessions: Annotated[CreateSession, Depends(get_create_session)],
    sign: Annotated[SignToken, Depends(get_sign_refresh_token)],
) -> OpenUserSession:
    """Собирает сценарий открытия сессии.

    Args:
        db (AsyncSession): Сессия базы данных для доступа к учётным записям.
        sessions (CreateSession): Сценарий создания сессии.
        sign (SignToken): Подписывает refresh-токен.

    Returns:
        OpenUserSession: Сценарий входа и открытия сессии.
    """
    return OpenUserSession(SqlAlchemyUserRepository(db), PASSWORD_HASHER, sessions, sign)


async def get_refresh_user_session(
    rotate: Annotated[RotateRefreshToken, Depends(get_rotate_refresh_token)],
    users: Annotated[GetUser, Depends(get_user)],
    issue: Annotated[IssueTokenPair, Depends(get_issue_token_pair)],
) -> RefreshUserSession:
    """Собирает сценарий обновления сессии.

    Args:
        rotate (RotateRefreshToken): Сценарий ротации refresh-токена.
        users (GetUser): Сценарий получения учётной записи.
        issue (IssueTokenPair): Сценарий выпуска пары токенов.

    Returns:
        RefreshUserSession: Сценарий обновления сессии и выпуска токенов.
    """
    return RefreshUserSession(rotate, users, issue)
