from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis

from src.providers.cache import StorageNumber, get_bounded_client
from src.providers.cache.repositories import PublicJWKRepository
from src.services.jwk import JWKPublishingService


async def get_jwk_publishing_service(
    client: Annotated[Redis, Depends(get_bounded_client(StorageNumber.KEYS.value))],
) -> JWKPublishingService:
    """Предоставляет сервис публикации публичных JWK на время запроса.

    Клиент Redis берётся из пула БД публичных ключей и закрывается вместе с запросом.

    Returns:
        JWKPublishingService: Сервис, привязанный к кешу публичных ключей.
    """

    return JWKPublishingService(jwk_repository=PublicJWKRepository(client))
