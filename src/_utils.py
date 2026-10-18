from collections.abc import Awaitable, Callable, Mapping
from typing import Literal, NamedTuple

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import Response

type CallNext = Callable[[Request], Awaitable[Response]]
type ExceptionsHandlingMap = Mapping[int | type[Exception], Callable]


class MiddlewareRecord(NamedTuple):
    """Аннотация для элемента списка регистируемых Middleware."""

    type: Literal["http"]
    middleware: Callable[[Request, CallNext], Awaitable[Response]]


class MiddlewaresRegistrator:
    """Утилитарный класс для удобной регистрации Middleware в экземпляре
    приложения FastAPI.
    """

    def __init__(self, middlewares: list[MiddlewareRecord]) -> None:
        """Инициализация класса.

        Args:
            middlewares (list[MiddlewareRecord]): Список регистрируемых
                Middlewares.
        """
        self._middlewares_data = middlewares

    def __call__(self, app: FastAPI) -> None:
        """Регистрирует Middlewares в переданном экземпляре приложения
        FastAPI.

        Args:
            app (FastAPI): экземпляр приложения FastAPI.
        """
        for type_, midlleware_func in self._middlewares_data:
            app.middleware(type_)(midlleware_func)


class ExceptionHandlersRegistrator:
    """Утилитарный класс для удорбной регистрации обработчиков исключений
    в экземпляре приложения FastAPI.
    """

    def __init__(self, handling_map: ExceptionsHandlingMap) -> None:
        """Инициализация класса.

        Args:
            handling_map (ExceptionsHandlingMap): Карта регистрируемых
                обработчиков исключений.
        """
        self._exceptions_handling_map = handling_map

    def __call__(self, app: FastAPI) -> None:
        """Регистрирует обработчики исключений в переданном экземпляре
        приложения FastAPI.

        Args:
            app (FastAPI): экземпляр приложения FastAPI.
        """
        for exception, handler in self._exceptions_handling_map.items():
            app.add_exception_handler(exception, handler=handler)
