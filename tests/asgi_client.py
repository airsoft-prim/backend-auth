"""Клиент ASGI-приложения без внешних зависимостей.

`fastapi.testclient` требует httpx, которого нет в зависимостях проекта, поэтому
HTTP-контракт проверяется вызовом ASGI-приложения напрямую: тот же путь проходят
маршрутизация, валидация схемы ответа и обработка ошибок.
"""

from collections.abc import Awaitable, Callable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
import json
from typing import Any

type ASGIMessage = MutableMapping[str, Any]
type ASGIApp = Callable[
    [ASGIMessage, Callable[[], Awaitable[ASGIMessage]], Callable[[ASGIMessage], Awaitable[None]]],
    Awaitable[None],
]

__all__ = ["ASGIClient", "ASGIResponse"]


@dataclass(frozen=True, slots=True)
class ASGIResponse:
    """Ответ ASGI-приложения."""

    status_code: int
    headers: Mapping[str, str]
    body: bytes

    @property
    def payload(self) -> Any:
        """Тело ответа, разобранное как JSON.

        Returns:
            Any: Данные ответа.
        """
        return json.loads(self.body)


class ASGIClient:
    """Клиент приложения: обёртка над вызовом ASGI."""

    def __init__(self, app: ASGIApp) -> None:
        """Инициализация клиента.

        Args:
            app (ASGIApp): ASGI-приложение.
        """
        self._app = app

    async def get(self, path: str) -> ASGIResponse:
        """Запрашивает путь методом GET.

        Args:
            path (str): Путь запроса.

        Returns:
            ASGIResponse: Ответ приложения.
        """
        return await self.request("GET", path)

    async def post(self, path: str) -> ASGIResponse:
        """Запрашивает путь методом POST.

        Args:
            path (str): Путь запроса.

        Returns:
            ASGIResponse: Ответ приложения.
        """
        return await self.request("POST", path)

    async def request(self, method: str, path: str) -> ASGIResponse:
        """Отправляет запрос в приложение.

        Args:
            method (str): HTTP-метод.
            path (str): Путь запроса.

        Returns:
            ASGIResponse: Ответ приложения.
        """
        messages: list[ASGIMessage] = []

        async def receive() -> ASGIMessage:
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: ASGIMessage) -> None:
            messages.append(message)

        scope: ASGIMessage = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": method.upper(),
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "root_path": "",
            "scheme": "http",
            "headers": [(b"host", b"testserver")],
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
        }

        try:
            await self._app(scope, receive, send)
        except Exception:  # Starlette отправляет ответ 500 и перевыбрасывает ошибку
            if not messages:
                raise

        return self._collect(messages)

    @staticmethod
    def _collect(messages: Sequence[ASGIMessage]) -> ASGIResponse:
        """Собирает ответ из сообщений ASGI.

        Args:
            messages (Sequence[ASGIMessage]): Сообщения, отправленные приложением.

        Raises:
            RuntimeError: Приложение не отправило ответ.

        Returns:
            ASGIResponse: Код состояния, заголовки и тело ответа.
        """
        starts = [message for message in messages if message["type"] == "http.response.start"]
        bodies = [
            message.get("body", b"")
            for message in messages
            if message["type"] == "http.response.body"
        ]

        if not starts:
            msg = "ASGI application did not send a response."
            raise RuntimeError(msg)

        start = starts[0]
        headers = {key.decode().lower(): value.decode() for key, value in start["headers"]}

        return ASGIResponse(status_code=start["status"], headers=headers, body=b"".join(bodies))
