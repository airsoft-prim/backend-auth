from collections.abc import Sequence
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


# TODO: Реализовать
async def pref_counting_middleware(request: Request, call_next: CallNext) -> Response:
    raise NotImplementedError


_midllewares: Sequence[MiddlewareRecord] = [
    MiddlewareRecord("http", trace_request_middleware),
    MiddlewareRecord("http", pref_counting_middleware),
]

register_middlewares = MiddlewaresRegistrator(_midllewares)
