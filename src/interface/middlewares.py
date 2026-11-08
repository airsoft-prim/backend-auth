from collections.abc import Sequence
from math import ceil
import time
from time import monotonic
from typing import ClassVar
from uuid import uuid7

from fastapi import status
from fastapi.requests import Request
from fastapi.responses import JSONResponse, Response
from loguru import logger

from src.config import config

from ._utils import CallNext, MiddlewareRecord, MiddlewaresRegistrator


class RateLimitingMiddleware:
    """Middleware ограничения частоты HTTP-запросов по IP.

    Применяет `REQUEST_RATE_LIMIT` ко всем HTTP-путям за фиксированное окно `REQUEST_RATE_WINDOW` в
    секундах. Счётчики хранятся в памяти процесса и сбрасываются при смене окна; превышение лимита
    возвращает ответ `429`.
    """

    def __init__(self) -> None:
        """Инициализация класса."""
        self._counts: dict[str, int] = {}
        self._window = -1

    # TODO: Заменить фиксированное окно на скользящее окно с общим хранилищем Redis.
    async def __call__(self, request: Request, call_next: CallNext) -> Response:
        """Пропускает запрос в пределах лимита или возвращает ответ `429`.

        Запросы без адреса клиента учитываются под общим ключом `unknown`. Отклонённые запросы не
        передаются следующему обработчику.

        Args:
            request (Request): HTTP-запрос с адресом клиента для учёта лимита.
            call_next (CallNext): Следующий обработчик HTTP-запроса.

        Returns:
            Response: Ответ следующего обработчика либо ответ `429` с заголовком `Retry-After`,
                содержащим время до конца окна в секундах, округлённое вверх.
        """

        now = monotonic()
        window = int(now // config.security.REQUEST_RATE_WINDOW)

        if window != self._window:
            self._counts.clear()
            self._window = window

        ip = request.client.host if request.client else "unknown"
        count = self._counts.get(ip, 0)

        if count >= config.security.REQUEST_RATE_LIMIT:
            retry_after = ceil((window + 1) * config.security.REQUEST_RATE_WINDOW - now)
            return self._block_request(retry_after)

        self._counts[ip] = count + 1
        return await call_next(request)

    @staticmethod
    def _block_request(retry_after: int) -> JSONResponse:
        """Создаёт ответ `429` с заголовком `Retry-After` в секундах."""
        return JSONResponse(
            {"detail": "Too many requests."},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
        )


class TraceRequestMiddleware:
    """Middleware трассировки HTTP-запросов по идентификатору.

    Связывает записи логов с идентификатором запроса, сохраняет его в `request.state` и возвращает
    в заголовке `X-Request-ID`. Маршруты из `EXCLUDE_ROUTES` передаются следующему обработчику без
    трассировки.
    """

    EXCLUDE_ROUTES: ClassVar[frozenset[str]] = frozenset(
        {
            "/favicon.ico",
            "/health/liveness",
            "/health/readiness",
        }
    )

    async def __call__(self, request: Request, call_next: CallNext) -> Response:
        """Добавляет контекст трассировки и заголовок `X-Request-ID`.

        Использует первый непустой заголовок `X-Request-ID` или `X-Correlation-ID`; при их
        отсутствии создаёт UUIDv7. Сохраняет идентификатор в `request.state.request_id` и логирует
        результат обработки.

        Args:
            request (Request): HTTP-запрос с маршрутом и заголовками трассировки.
            call_next (CallNext): Следующий обработчик HTTP-запроса.

        Returns:
            Response: Ответ следующего обработчика с `X-Request-ID` либо исходный ответ для
                маршрута из `EXCLUDE_ROUTES`.
        """
        if request.url.path in self.EXCLUDE_ROUTES:
            return await call_next(request)

        trace_id = self._get_trace_id(request)
        with logger.contextualize(request_id=trace_id):
            logger.bind(route=request.url.path, method=request.method).info("Request acquired.")

            request.state.request_id = trace_id
            response = await call_next(request)

            self._log_response(request, response)

        response.headers["X-Request-ID"] = trace_id
        return response

    @staticmethod
    def _get_trace_id(request: Request) -> str:
        """Выбирает `X-Request-ID`, затем `X-Correlation-ID`, иначе создаёт UUIDv7 в `hex`."""
        return (
            request.headers.get("X-Request-ID")
            or request.headers.get("X-Correlation-ID")
            or uuid7().hex
        )

    @staticmethod
    def _log_response(request: Request, response: Response) -> None:
        """Логирует завершение запроса, предупреждение при 4xx/5xx и ошибку при 5xx."""
        log_bind = logger.bind(route=request.url.path, method=request.method)

        if response.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            log_bind.error("Request failed with server error.")

        if response.status_code >= status.HTTP_400_BAD_REQUEST:
            log_bind.warning("Request failed with client error.")

        log_bind.success("Request handled.")


class PerfCountingMiddleware:
    """Middleware измерения длительности обработки HTTP-запросов.

    Измеряет время работы следующего обработчика через `perf_counter` и записывает миллисекунды в
    заголовок `X-Response-Time` и лог. Маршруты из `EXCLUDE_ROUTES` передаются следующему
    обработчику без измерения.
    """

    EXCLUDE_ROUTES: ClassVar[frozenset[str]] = frozenset(
        {
            "/favicon.ico",
            "/health/liveness",
            "/health/readiness",
        }
    )

    async def __call__(self, request: Request, call_next: CallNext) -> Response:
        """Добавляет время обработки в заголовок `X-Response-Time` и лог.

        Args:
            request (Request): HTTP-запрос с маршрутом для проверки исключений.
            call_next (CallNext): Следующий обработчик HTTP-запроса.

        Returns:
            Response: Ответ с `X-Response-Time` в миллисекундах, округлённых до двух знаков после
                запятой, либо исходный ответ для исключённого маршрута.
        """
        if request.url.path in self.EXCLUDE_ROUTES:
            return await call_next(request)

        started_at = time.perf_counter()
        response = await call_next(request)
        self._record_duration(request, response, started_at)
        return response

    @staticmethod
    def _record_duration(request: Request, response: Response, started_at: float) -> None:
        """Записывает в ответ и лог миллисекунды с момента `started_at` из `perf_counter`."""
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        response.headers["X-Response-Time"] = str(duration_ms)

        bound = logger.bind(route=request.url.path, method=request.method, duration_ms=duration_ms)
        bound.debug("Request processed.")


_midllewares: Sequence[MiddlewareRecord] = [
    MiddlewareRecord("http", RateLimitingMiddleware()),
    MiddlewareRecord("http", TraceRequestMiddleware()),
    MiddlewareRecord("http", PerfCountingMiddleware()),
]

register_middlewares = MiddlewaresRegistrator(_midllewares)
