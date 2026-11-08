from collections.abc import Awaitable, Callable, Mapping
from enum import Enum
from typing import Any, Literal, NamedTuple, TypedDict

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import Response

type CallNext = Callable[[Request], Awaitable[Response]]
type ExceptionsHandlingMap = Mapping[int | type[Exception], Callable]


class MiddlewareRecord(NamedTuple):
    """Аннотация для элемента списка регистируемых Middleware.

    Связывает тип http с асинхронным обработчиком запроса. Используется `MiddlewaresRegistrator`
    при подключении `middleware` к `FastAPI`.
    """

    type: Literal["http"]
    middleware: Callable[[Request, CallNext], Awaitable[Response]]


class MiddlewaresRegistrator:
    """Регистратор HTTP-`middleware` в `FastAPI`.

    Сохраняет список обработчиков и регистрирует каждый через `app.middleware` в порядке списка.
    Поддерживает функции и экземпляры с асинхронным `__call__`.
    """

    def __init__(self, middlewares: list[MiddlewareRecord]) -> None:
        """Инициализация класса.

        Args:
            middlewares (list[MiddlewareRecord]): Список регистрируемых Middlewares.
        """
        self._middlewares_data = middlewares

    def __call__(self, app: FastAPI) -> None:
        """Регистрирует Middlewares в переданном экземпляре приложения `FastAPI`.

        Args:
            app (FastAPI): экземпляр приложения `FastAPI`.
        """
        for type_, midlleware_func in self._middlewares_data:
            app.middleware(type_)(midlleware_func)


class ExceptionHandlersRegistrator:
    """Регистратор обработчиков исключений `FastAPI`.

    Сохраняет соответствие кодов состояния или классов исключений обработчикам и подключает его к
    экземпляру `FastAPI`.
    """

    def __init__(self, handling_map: ExceptionsHandlingMap) -> None:
        """Инициализация класса.

        Args:
            handling_map (ExceptionsHandlingMap): Карта регистрируемых обработчиков исключений.
        """
        self._exceptions_handling_map = handling_map

    def __call__(self, app: FastAPI) -> None:
        """Регистрирует обработчики исключений в переданном экземпляре приложения `FastAPI`.

        Args:
            app (FastAPI): экземпляр приложения `FastAPI`.
        """
        for exception, handler in self._exceptions_handling_map.items():
            app.add_exception_handler(exception, handler=handler)


class RouteDocs(TypedDict, total=False):
    """Формат документирующих данных к пути API.

    Описывает параметры документации маршрута для передачи в декораторы `FastAPI`, включая
    `summary`, `description`, `responses` и примеры ответа.
    """

    summary: str
    operation_id: str
    description: str
    deprecated: bool
    tags: list[str | Enum]
    status_code: int
    response_description: str
    responses: dict[int | str, dict[str, Any]] | None
