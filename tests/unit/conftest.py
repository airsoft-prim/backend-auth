"""Фикстуры слоя unit: подмена планировщика ротации и подпись токенов для проверки."""

from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import jwt
import pytest

from src.general.security import SIGNING_ALGORITHM
from src.providers.filesystem.repositories import PrivateJWKRepository

__all__ = [
    "RawTokenSigner",
    "RecordingEventLoop",
    "RotationInterruptedError",
    "patch_daemon_sleep",
    "raw_token_signer",
]

type RawTokenSigner = Callable[[dict[str, Any], str | None], str]


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


@pytest.fixture
def raw_token_signer(key_store_dir: Path) -> RawTokenSigner:
    """Отдаёт функцию подписи токена приватным ключом сервиса.

    Нужна там, где проверяющий сервис должен получить токен с неверными или
    неполными claims: обычный сервис выпуска всегда собирает корректный набор.

    Args:
        key_store_dir (Path): Каталог приватного ключа подписи.

    Returns:
        RawTokenSigner: Функция «claims, kid → подписанный токен»; `kid=None`
            оставляет заголовок без идентификатора ключа.
    """

    def _sign(claims: dict[str, Any], key_id: str | None) -> str:
        key_file = key_store_dir / PrivateJWKRepository.FILE_NAME
        private_key = serialization.load_pem_private_key(key_file.read_bytes(), password=None)

        if not isinstance(private_key, Ed25519PrivateKey):
            msg = "Key store holds a key that is not Ed25519."
            raise TypeError(msg)

        headers = {} if key_id is None else {"kid": key_id}

        return jwt.encode(claims, private_key, algorithm=SIGNING_ALGORITHM, headers=headers)

    return _sign
