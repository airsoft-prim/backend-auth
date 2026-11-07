from unittest.mock import AsyncMock

from fastapi import status
from fastapi.requests import Request
from fastapi.responses import Response
import pytest

from src.config import config
from src.interface.middlewares import RateLimitingMiddleware


@pytest.fixture(autouse=True)
def rate_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.security, "REQUEST_RATE_LIMIT", 60)
    monkeypatch.setattr(config.security, "REQUEST_RATE_WINDOW", 60)


@pytest.mark.parametrize("path", ["/auth/login", "/health/liveness", "/docs"])
async def test_limit_blocks_excess_requests_and_resets(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    middleware = RateLimitingMiddleware()
    call_next = AsyncMock(return_value=Response(status_code=204))
    request = Request({"type": "http", "path": path, "client": ("192.0.2.1", 1234)})
    monkeypatch.setattr("src.interface.middlewares.monotonic", lambda: 120.5)

    for _ in range(config.security.REQUEST_RATE_LIMIT):
        assert (await middleware(request, call_next)).status_code == status.HTTP_204_NO_CONTENT

    response = await middleware(request, call_next)
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert response.headers["Retry-After"] == "60"
    assert call_next.await_count == config.security.REQUEST_RATE_LIMIT

    other_ip = Request({"type": "http", "client": ("192.0.2.2", 1234)})
    assert (await middleware(other_ip, call_next)).status_code == status.HTTP_204_NO_CONTENT

    monkeypatch.setattr("src.interface.middlewares.monotonic", lambda: 179.5)
    assert (await middleware(request, call_next)).headers["Retry-After"] == "1"
    monkeypatch.setattr("src.interface.middlewares.monotonic", lambda: 180.0)
    assert (await middleware(request, call_next)).status_code == status.HTTP_204_NO_CONTENT


async def test_missing_client_is_limited_and_forwarded_header_cannot_bypass_limit() -> None:
    middleware = RateLimitingMiddleware()
    call_next = AsyncMock(return_value=Response(status_code=204))
    for number in range(config.security.REQUEST_RATE_LIMIT + 1):
        request = Request({"type": "http", "headers": [(b"x-forwarded-for", str(number).encode())]})
        response = await middleware(request, call_next)

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert call_next.await_count == config.security.REQUEST_RATE_LIMIT
