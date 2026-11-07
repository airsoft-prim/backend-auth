from collections.abc import Sequence
from math import ceil
import time
from time import monotonic
from typing import Final
from uuid import uuid7

from fastapi import status
from fastapi.requests import Request
from fastapi.responses import JSONResponse, Response
from loguru import logger

from src.config import config

from ._utils import CallNext, MiddlewareRecord, MiddlewaresRegistrator

EXCLUDED_PATHS: Final[set[str]] = {
    "/favicon.ico",
    "/health/liveness",
    "/health/readiness",
}


class RateLimitingMiddleware:
    """Ограничивает число запросов на IP за настраиваемое фиксированное окно.

    Счётчики хранятся в памяти процесса и сбрасываются при смене окна.
    """

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}
        self._window = -1

    # TODO: Заменить фиксированное окно на скользящее окно с общим хранилищем Redis.
    async def __call__(self, request: Request, call_next: CallNext) -> Response:
        """Ограничивает все HTTP-пути, возвращая 429 и Retry-After."""

        now = monotonic()
        window = int(now // config.security.REQUEST_RATE_WINDOW)

        if window != self._window:
            self._counts.clear()
            self._window = window

        ip = request.client.host if request.client else "unknown"
        count = self._counts.get(ip, 0)

        if count >= config.security.REQUEST_RATE_LIMIT:
            return self._block_request(
                ceil((window + 1) * config.security.REQUEST_RATE_WINDOW - now)
            )

        self._counts[ip] = count + 1
        return await call_next(request)

    @staticmethod
    def _block_request(retry_after: int) -> JSONResponse:
        """Возвращает отказ с временем ожидания до следующего запроса в секундах."""
        return JSONResponse(
            {"detail": "Too many requests."},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
        )


async def trace_request_middleware(request: Request, call_next: CallNext) -> Response:
    """Middleware для трассировки запроса.

    Присваивает каждому запросу уникальный идентификатор, сопровождающий все
    действия приложения в процессе формирования ответа на запрос.
    """
    if (route := request.url.path) in EXCLUDED_PATHS:
        return await call_next(request)

    id_header = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID")
    trace_id = id_header or str(uuid7().hex)

    with logger.contextualize(request_id=trace_id):
        log_bind = logger.bind(route=route, method=request.method)

        log_bind.info("Request acquired.")

        request.state["request_id"] = trace_id
        response = await call_next(request)

        if response.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            log_bind.error("Request failed with server error.")

        if response.status_code >= status.HTTP_400_BAD_REQUEST:
            log_bind.warning("Request failed with client error.")

        log_bind.success("Request handled.")

    response.headers["X-Request-ID"] = trace_id
    return response


async def perf_counting_middleware(request: Request, call_next: CallNext) -> Response:
    """Middleware для подсчёта времени обработки запроса.

    Замеряет длительность обработки запроса и возвращает её клиенту в заголовке
    ``X-Response-Time`` в миллисекундах. Служебные пути не замеряются, чтобы
    пробы не искажали метрику собственным оверхедом.
    """
    if (route := request.url.path) in EXCLUDED_PATHS:
        return await call_next(request)

    started_at = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)

    response.headers["X-Response-Time"] = str(duration_ms)

    log_bind = logger.bind(route=route, method=request.method, duration_ms=duration_ms)
    log_bind.debug("Request processed.")

    return response


_midllewares: Sequence[MiddlewareRecord] = [
    MiddlewareRecord("http", RateLimitingMiddleware()),
    MiddlewareRecord("http", trace_request_middleware),
    MiddlewareRecord("http", perf_counting_middleware),
]

register_middlewares = MiddlewaresRegistrator(_midllewares)
