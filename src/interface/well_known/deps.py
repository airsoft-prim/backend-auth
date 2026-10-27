from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis

from src.adapters.cache import StorageNumber, get_bounded_client
from src.adapters.cache.repositories import RedisPublicJwkRepository
from src.application.jwk import CollectJwks


async def get_collect_jwks(
    client: Annotated[Redis, Depends(get_bounded_client(StorageNumber.KEYS.value))],
) -> CollectJwks:
    """Предоставляет use case сбора публичных JWK на время запроса.

    Клиент Redis берётся из пула БД публичных ключей и закрывается вместе с запросом.

    Args:
        client (Redis): Клиент Redis с опубликованными публичными JWK.

    Returns:
        CollectJwks: Use case, привязанный к кешу публичных ключей.
    """
    return CollectJwks(RedisPublicJwkRepository(client))
