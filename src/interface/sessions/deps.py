from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis

from src.adapters.cache import StorageNumber, get_bounded_client
from src.adapters.cache.repositories import RedisRevokedSessionsRepository, RedisSessionRepository
from src.application.session import CloseSession, ListSessions
from src.domain.errors import JWTDecryptionError
from src.domain.tokens import RefreshTokenClaims
from src.interface.auth.deps import get_refresh_token


@dataclass(frozen=True, slots=True)
class CurrentSession:
    """Текущая сессия запроса: владелец и идентификатор из проверенного токена.

    Передаёт в маршруты управления сессиями числовой `user_id` и строковый `sid` из проверенных
    `claims` `refresh`-токена.
    """

    user_id: int
    sid: str


async def get_current_session(
    claims: Annotated[RefreshTokenClaims, Depends(get_refresh_token)],
) -> CurrentSession:
    """Возвращает владельца и идентификатор сессии из проверенного `refresh`-токена.

    Args:
        claims (RefreshTokenClaims): Проверенные `claims` `refresh`-токена.

    Returns:
        CurrentSession: Владелец и `sid` сессии запроса.

    Raises:
        JWTDecryptionError: В `sub` токена не числовой идентификатор пользователя.
    """
    try:
        user_id = int(claims["sub"])

    except (TypeError, ValueError) as error:
        msg = "Token subject is invalid."
        raise JWTDecryptionError(msg) from error

    return CurrentSession(user_id=user_id, sid=claims["sid"])


async def get_list_sessions(
    client: Annotated[Redis, Depends(get_bounded_client(StorageNumber.SESSIONS.value))],
) -> ListSessions:
    """Предоставляет use case получения активных сессий на время запроса.

    Args:
        client (Redis): Клиент `Redis` с сессиями пользователей.

    Returns:
        ListSessions: Use case списка активных сессий.
    """
    return ListSessions(RedisSessionRepository(client))


async def get_close_session(
    tokens_client: Annotated[Redis, Depends(get_bounded_client(StorageNumber.TOKENS.value))],
    sessions_client: Annotated[Redis, Depends(get_bounded_client(StorageNumber.SESSIONS.value))],
) -> CloseSession:
    """Предоставляет use case закрытия сессии на время запроса.

    Args:
        tokens_client (Redis): Клиент `Redis` с отозванными сессиями.
        sessions_client (Redis): Клиент `Redis` с сессиями пользователей.

    Returns:
        CloseSession: Use case закрытия одной сессии.
    """
    return CloseSession(
        RedisRevokedSessionsRepository(tokens_client),
        RedisSessionRepository(sessions_client),
    )
