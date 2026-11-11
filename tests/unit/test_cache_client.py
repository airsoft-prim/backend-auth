"""Проверка подключения Redis с учётными данными и без них."""

from types import SimpleNamespace

import pytest

from src.adapters.cache import client
from src.config.cache import CacheConfiguration


@pytest.mark.parametrize(
    ("username", "password", "expected"),
    [
        (None, None, {}),
        (None, "test-secret", {}),
        ("test-user", None, {}),
        ("test-user", "test-secret", {"username": "test-user", "password": "test-secret"}),
    ],
)
def test_redis_pools_receive_credentials(
    monkeypatch: pytest.MonkeyPatch,
    username: str | None,
    password: str | None,
    expected: dict[str, str],
) -> None:
    """Учётные данные применяются к каждому пулу независимо от номера БД."""
    cache = CacheConfiguration(USER=username, PSWD=password)
    monkeypatch.setattr(client, "config", SimpleNamespace(cache=cache))
    monkeypatch.setattr(client, "_pools", {})

    for database in (0, 1, 2):
        kwargs = client._get_pool(database).connection_kwargs  # noqa: SLF001
        assert kwargs["db"] == database
        assert {key: kwargs.get(key) for key in ("username", "password")} == {
            key: expected.get(key) for key in ("username", "password")
        }
