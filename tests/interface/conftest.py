"""Фикстуры слоя interface: клиенты эндпоинтов JWKS и регистрации."""

from collections.abc import Callable

from fastapi import FastAPI
import pytest

from src.adapters.cache.repositories import RedisPublicJwkRepository
from src.application.jwk import CollectJwks
from src.interface.auth.deps import get_register_user
from src.interface.well_known.deps import get_collect_jwks
from tests.asgi_client import ASGIClient

__all__ = [
    "JWKSClientFactory",
    "RegisterClientFactory",
    "StubUserService",
    "jwks_client_factory",
    "register_client_factory",
]


class StubUserService:
    """Подмена сервиса учётных записей: запоминает вызов или поднимает заданную ошибку.

    Маршрут проверяется без БД: аргументы вызова запоминаются — так тест видит, что
    маршрут передал сервису логин, адрес и пароль в открытом виде.
    """

    def __init__(self, *, error: Exception | None = None) -> None:
        """Инициализация подмены.

        Args:
            error (Exception | None, optional): Ошибка, которую регистрация поднимет
                вместо записи учётной записи. Defaults to None.
        """
        self._error = error
        self.received: dict[str, str] | None = None

    async def __call__(self, *, username: str, email: str, password: str) -> None:
        """Запоминает данные регистрации или поднимает заданную ошибку.

        Args:
            username (str): Логин учётной записи.
            email (str): Адрес электронной почты учётной записи.
            password (str): Пароль учётной записи в открытом виде.

        Raises:
            Exception: Ошибка, переданная в подмену.
        """
        self.received = {"username": username, "email": email, "password": password}

        if self._error is not None:
            raise self._error


type JWKSClientFactory = Callable[[RedisPublicJwkRepository], ASGIClient]
type RegisterClientFactory = Callable[[StubUserService], ASGIClient]


@pytest.fixture
def jwks_client_factory(api_app: FastAPI) -> JWKSClientFactory:
    """Собирает клиент JWKS с указанным репозиторием публичных ключей.

    Подменяется только репозиторий: маршрутизация, схемы ответа и обработка ошибок
    остаются настоящими.

    Args:
        api_app (FastAPI): Приложение под тестом.

    Returns:
        JWKSClientFactory: Фабрика клиентов эндпоинта.
    """

    def _factory(repository: RedisPublicJwkRepository) -> ASGIClient:
        api_app.dependency_overrides[get_collect_jwks] = lambda: CollectJwks(jwks=repository)

        return ASGIClient(api_app)

    return _factory


@pytest.fixture
def register_client_factory(api_app: FastAPI) -> RegisterClientFactory:
    """Собирает клиент регистрации с указанным сервисом учётных записей.

    Подменяется только сервис: маршрутизация, валидация тела запроса, сборка ответа и
    обработка ошибок остаются настоящими.

    Args:
        api_app (FastAPI): Приложение под тестом.

    Returns:
        RegisterClientFactory: Фабрика клиентов маршрута регистрации.
    """

    def _factory(service: StubUserService) -> ASGIClient:
        api_app.dependency_overrides[get_register_user] = lambda: service

        return ASGIClient(api_app)

    return _factory
