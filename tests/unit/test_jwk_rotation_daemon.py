"""Тесты демона ротации приватного JWK."""

from asyncio import EventLoop
from pathlib import Path
from typing import cast

import pytest

from src.providers.filesystem.repositories import PrivateJWKRepository
from src.rotation.daemon import JWKRotationDaemon
from src.services.jwk import JWKGenerationService
from tests.doubles import InMemoryRedis
from tests.unit.conftest import (
    RecordingEventLoop,
    RotationInterruptedError,
    patch_daemon_sleep,
)

CRON_RULE = "0 0 * * *"
DAY_IN_SECONDS = 24 * 60 * 60
PUBLISHED_KEYS_AFTER_ROTATION = 2


async def test_daemon_rotates_key_immediately_on_start(
    monkeypatch: pytest.MonkeyPatch,
    jwk_service: JWKGenerationService,
    key_store_dir: Path,
    redis_double: InMemoryRedis,
) -> None:
    """Первый запуск демона ротации.

    Given: каталог ключей пуст, а расписание ротации задано,
    When: демон запускается,
    Then: ключ подписи появляется сразу, не дожидаясь ближайшего момента по расписанию.
    """
    # Дано
    delays = patch_daemon_sleep(monkeypatch, rotations=1)
    event_loop = RecordingEventLoop()
    daemon = JWKRotationDaemon(jwk_service, CRON_RULE, event_loop=cast("EventLoop", event_loop))

    # Когда
    daemon.start()
    with pytest.raises(RotationInterruptedError, match="Rotation loop interrupted"):
        await event_loop.scheduled[0]

    # Тогда
    assert delays[0] == 0
    assert (key_store_dir / PrivateJWKRepository.FILE_NAME).exists()
    assert len(redis_double.values) == 1


async def test_daemon_overwrites_key_and_expires_previous_public_key(
    monkeypatch: pytest.MonkeyPatch,
    jwk_service: JWKGenerationService,
    key_store_dir: Path,
    redis_double: InMemoryRedis,
) -> None:
    """Ротация после первого запуска.

    Given: ключ уже сгенерирован и опубликован, а демон запускается заново,
    When: демон проходит первый запуск и одну ротацию по расписанию,
    Then: приватный ключ перезаписывается, а прошлый публичный ключ получает время
    жизни, равное интервалу расписания, — выданные ранее токены ещё проверяемы.
    """
    # Дано
    key_file = key_store_dir / PrivateJWKRepository.FILE_NAME
    previous = await jwk_service.generate_jwk(DAY_IN_SECONDS)
    previous_key_file = key_file.read_bytes()

    delays = patch_daemon_sleep(monkeypatch, rotations=2)
    event_loop = RecordingEventLoop()
    daemon = JWKRotationDaemon(jwk_service, CRON_RULE, event_loop=cast("EventLoop", event_loop))

    # Когда
    daemon.start()
    with pytest.raises(RotationInterruptedError, match="Rotation loop interrupted"):
        await event_loop.scheduled[0]

    # Тогда
    assert delays[0] == 0
    assert key_file.read_bytes() != previous_key_file
    assert redis_double.ttl == {f"jwk:{previous.key_id}": DAY_IN_SECONDS}
    assert len(redis_double.values) == PUBLISHED_KEYS_AFTER_ROTATION


async def test_daemon_takes_running_loop_when_loop_is_not_given(
    monkeypatch: pytest.MonkeyPatch,
    jwk_service: JWKGenerationService,
    key_store_dir: Path,
    redis_double: InMemoryRedis,
) -> None:
    """Цикл событий без явно переданного цикла.

    Given: демон собран без переданного цикла событий, — так его собирает lifespan
        приложения,
    When: демон запускается,
    Then: задача ротации ставится в текущий цикл, а не теряется.
    """
    # Дано: цикл не передан, поэтому демон должен взять текущий
    patch_daemon_sleep(monkeypatch, rotations=1)
    event_loop = RecordingEventLoop()
    daemon = JWKRotationDaemon(jwk_service, CRON_RULE)

    # Когда
    with monkeypatch.context() as patch:
        patch.setattr("src.rotation.daemon.asyncio.get_running_loop", lambda: event_loop)
        daemon.start()

    # Тогда
    with pytest.raises(RotationInterruptedError, match="Rotation loop interrupted"):
        await event_loop.scheduled[0]

    assert (key_store_dir / PrivateJWKRepository.FILE_NAME).exists()
    assert len(redis_double.values) == 1
