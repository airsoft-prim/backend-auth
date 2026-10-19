"""Тесты публикации ключей подписи на настоящем Redis."""

from pathlib import Path

from fastapi import status
import pytest
from redis.asyncio import Redis

from src.providers.cache.repositories import PublicJWKRepository
from src.services.jwk import JWKGenerationService
from tests.asgi_client import ASGIClient

JWKS_PATH = "/.well-known/jwks.json"
KEY_TTL_SECONDS = 3600
SHORT_TTL_SECONDS = 60
MILLISECONDS_PER_SECOND = 1000

pytestmark = pytest.mark.integration


async def test_jwks_endpoint_serves_key_published_in_redis(
    redis_client: Redis,
    api_client: ASGIClient,
    key_store_dir: Path,
) -> None:
    """Ключ, опубликованный в Redis, в ответе эндпоинта.

    Given: настоящий Redis и сервис генерации ключей,
    When: ключ опубликован в Redis, а потребитель запрашивает JWKS,
    Then: эндпоинт отдаёт этот ключ без приватной части.
    """
    # Дано
    service = JWKGenerationService(key_store_dir, PublicJWKRepository(redis_client))
    published = await service.generate_jwk(KEY_TTL_SECONDS)

    # Когда
    try:
        response = await api_client.get(JWKS_PATH)

        # Тогда
        assert response.status_code == status.HTTP_200_OK

        keys = response.payload["keys"]
        assert published.key_id in {key["kid"] for key in keys}

        key = next(key for key in keys if key["kid"] == published.key_id)
        assert "d" not in key
    finally:
        # Очистка: тест не оставляет своих ключей в БД публичных ключей
        await redis_client.delete(f"jwk:{published.key_id}")


async def test_rotated_key_gets_time_to_live(
    redis_client: Redis,
    key_store_dir: Path,
) -> None:
    """Время жизни прошлого публичного ключа.

    Given: сервис сгенерировал ключ и опубликовал его в Redis,
    When: ключ ротирован,
    Then: прошлый публичный ключ остаётся в Redis, но ограничен временем жизни.
    """
    # Дано
    service = JWKGenerationService(key_store_dir, PublicJWKRepository(redis_client))
    previous = await service.generate_jwk(KEY_TTL_SECONDS)
    previous_name = f"jwk:{previous.key_id}"
    created = [previous_name]

    # Когда
    try:
        rotated = await service.generate_jwk(KEY_TTL_SECONDS, overwrite=True)
        created.append(f"jwk:{rotated.key_id}")

        ttl_in_ms = await redis_client.pttl(previous_name)

        # Тогда
        assert ttl_in_ms > 0
        assert ttl_in_ms <= KEY_TTL_SECONDS * MILLISECONDS_PER_SECOND
        assert await redis_client.get(previous_name) is not None
    finally:
        # Очистка: тест не оставляет своих ключей в БД публичных ключей
        await redis_client.delete(*created)


async def test_repeated_rotation_keeps_ttl_of_older_key(
    redis_client: Redis,
    key_store_dir: Path,
) -> None:
    """Повторная ротация не продлевает срок ключей прошлых ротаций.

    Given: у ключа первой ротации уже ограничено время жизни,
    When: ключ ротирован ещё раз,
    Then: срок этого ключа не сбрасывается на новый TTL.
    """
    # Дано
    service = JWKGenerationService(key_store_dir, PublicJWKRepository(redis_client))
    older = await service.generate_jwk(KEY_TTL_SECONDS)
    older_name = f"jwk:{older.key_id}"
    created = [older_name]

    # Когда
    try:
        rotated = await service.generate_jwk(KEY_TTL_SECONDS, overwrite=True)
        created.append(f"jwk:{rotated.key_id}")

        await redis_client.expire(older_name, SHORT_TTL_SECONDS)

        repeated = await service.generate_jwk(KEY_TTL_SECONDS, overwrite=True)
        created.append(f"jwk:{repeated.key_id}")

        ttl_in_ms = await redis_client.pttl(older_name)

        # Тогда
        assert 0 < ttl_in_ms <= SHORT_TTL_SECONDS * MILLISECONDS_PER_SECOND
    finally:
        # Очистка: тест не оставляет своих ключей в БД публичных ключей
        await redis_client.delete(*created)
