"""Проверка индекса сессий на настоящем Redis."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from src.adapters.cache.repositories.session import _REMOVE_MISSING, RedisSessionRepository
from src.domain.entities import Session

pytestmark = pytest.mark.integration


async def test_session_index_lifetime_and_cleanup(redis_client: Redis) -> None:
    """Индекс живёт до последней сессии, а устаревшие ссылки удаляются безопасно."""
    user_id = uuid4().int
    now = datetime.now(UTC)
    long = Session(
        id=str(uuid4()), user_id=user_id, created_at=now, expires_at=now + timedelta(hours=2)
    )
    short = Session(
        id=str(uuid4()), user_id=user_id, created_at=now, expires_at=now + timedelta(hours=1)
    )
    index = f"session:user:{user_id}"
    long_key = f"session:{long.id}"
    short_key = f"session:{short.id}"
    repository = RedisSessionRepository(redis_client)

    try:
        assert await repository.list_active(user_id) == []
        await repository.save(long)
        long_ttl = await redis_client.ttl(index)
        await repository.save(short)
        assert await redis_client.ttl(index) >= long_ttl - 1

        await redis_client.delete(short_key)
        assert [session.id for session in await repository.list_active(user_id)] == [long.id]
        assert not await redis_client.sismember(index, short.id)

        # A save between the initial read and cleanup must retain the new index entry.
        await repository.save(short)
        await redis_client.eval(_REMOVE_MISSING, 2, short_key, index, short.id)
        assert await redis_client.sismember(index, short.id)
    finally:
        await redis_client.delete(index, long_key, short_key)
