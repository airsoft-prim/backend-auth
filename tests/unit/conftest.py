"""Фикстуры слоя unit: подмена планировщика демона ротации."""

from collections.abc import Coroutine
from typing import Any

import pytest

__all__ = ["RecordingEventLoop", "RotationInterruptedError", "patch_daemon_sleep"]


class RotationInterruptedError(Exception):
    """Сигнал остановки бесконечного цикла ротации в тесте."""


class RecordingEventLoop:
    """Подмена цикла событий: перехватывает задачу демона, не запуская её.

    Демон ротации использует от цикла только `is_closed` и `create_task`, поэтому
    подмена повторяет эти вызовы, а поставленную задачу отдаёт тесту для ожидания.
    """

    def __init__(self) -> None:
        """Инициализация подмены без поставленных задач."""
        self.scheduled: list[Coroutine[Any, Any, None]] = []

    def is_closed(self) -> bool:
        """Сообщает, что цикл открыт.

        Returns:
            bool: Всегда False — цикл подмены не закрывается.
        """
        return False

    def create_task(self, coroutine: Coroutine[Any, Any, None]) -> None:
        """Запоминает задачу демона вместо её запуска в цикле.

        Args:
            coroutine (Coroutine[Any, Any, None]): Задача, поставленная демоном.
        """
        self.scheduled.append(coroutine)


def patch_daemon_sleep(monkeypatch: pytest.MonkeyPatch, *, rotations: int) -> list[float]:
    """Подменяет паузу планировщика ротации и прерывает его цикл.

    Демон ротации работает бесконечно, поэтому заданное число ротаций выполняется, а
    следующая пауза прерывает цикл: тест проверяет ровно эти ротации.

    Args:
        monkeypatch (pytest.MonkeyPatch): Механизм подмены pytest.
        rotations (int): Число ротаций, которые должны выполниться до прерывания.

    Returns:
        list[float]: Длительности пауз, запрошенных планировщиком.
    """
    delays: list[float] = []

    async def _sleep(delay: float) -> None:
        delays.append(delay)

        if len(delays) > rotations:
            msg = "Rotation loop interrupted by the test."
            raise RotationInterruptedError(msg)

    monkeypatch.setattr("src.rotation.daemon.asyncio.sleep", _sleep)

    return delays
