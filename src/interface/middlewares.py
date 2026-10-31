from collections.abc import Sequence
import time
from typing import Final
from uuid import uuid7

from fastapi import status
from fastapi.requests import Request
from fastapi.responses import Response
from loguru import logger

from ._utils import CallNext, MiddlewareRecord, MiddlewaresRegistrator

EXCLUDED_PATHS: Final[set[str]] = {
    "/favicon.ico",
    "/health/liveness",
    "/health/readiness",
}


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
    MiddlewareRecord("http", trace_request_middleware),
    MiddlewareRecord("http", perf_counting_middleware),
]

register_middlewares = MiddlewaresRegistrator(_midllewares)
