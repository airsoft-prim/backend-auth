"""Клиент ASGI-приложения без внешних зависимостей.

`fastapi.testclient` требует httpx, которого нет в зависимостях проекта, поэтому HTTP-контракт
проверяется вызовом ASGI-приложения напрямую: тот же путь проходят маршрутизация, валидация схемы
ответа и обработка ошибок.
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
    """Ответ ASGI-приложения.

    Хранит код состояния, заголовки и байты тела. Свойство `payload` разбирает тело как JSON по
    запросу теста.
    """

    status_code: int
    headers: Mapping[str, str]
    body: bytes

    @property
    def payload(self) -> Any:
        """Тело ответа, разобранное как JSON."""
        return json.loads(self.body)


class ASGIClient:
    """Клиент приложения: обёртка над вызовом ASGI.

    Вызывает ASGI-приложение напрямую и собирает сообщения ответа без httpx. Поддерживает JSON-
    тело запроса и заголовки; `lifespan` автоматически не запускает.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Инициализация класса.

        Args:
            app (ASGIApp): ASGI-приложение.
        """
        self._app = app

    async def get(
        self,
        path: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> ASGIResponse:
        """Запрашивает путь методом GET.

        Args:
            path (str): Путь запроса.
            headers (Mapping[str, str] | None): Дополнительные заголовки запроса.

        Returns:
            ASGIResponse: Ответ приложения.
        """
        return await self.request("GET", path, headers=headers)

    async def post(
        self,
        path: str,
        payload: Any | None = None,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> ASGIResponse:
        """Запрашивает путь методом POST.

        Args:
            path (str): Путь запроса.
            payload (Any | None): Тело запроса: данные, сериализуемые в JSON. `None` — запрос без
                тела.
            headers (Mapping[str, str] | None): Дополнительные заголовки запроса.

        Returns:
            ASGIResponse: Ответ приложения.
        """
        return await self.request("POST", path, payload=payload, headers=headers)

    async def request(
        self,
        method: str,
        path: str,
        payload: Any | None = None,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> ASGIResponse:
        """Отправляет запрос в приложение.

        Args:
            method (str): HTTP-метод.
            path (str): Путь запроса.
            payload (Any | None): Тело запроса: данные, сериализуемые в JSON. `None` — запрос без
                тела.
            headers (Mapping[str, str] | None): Дополнительные заголовки запроса.

        Returns:
            ASGIResponse: Ответ приложения.

        Raises:
            Exception: Приложение выбросило исключение до отправки ответа.
        """
        messages: list[ASGIMessage] = []
        body = b"" if payload is None else json.dumps(payload).encode()
        request_headers = [(b"host", b"testserver")]

        if payload is not None:
            request_headers.append((b"content-type", b"application/json"))

        if headers is not None:
            request_headers.extend(
                (key.lower().encode(), value.encode()) for key, value in headers.items()
            )

        async def receive() -> ASGIMessage:
            """Возвращает ASGI-сообщение с телом HTTP-запроса.

            Returns:
                ASGIMessage: Сообщение `http.request` с полным телом запроса.
            """
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message: ASGIMessage) -> None:
            """Добавляет сообщение ASGI-ответа в буфер клиента.

            Args:
                message (ASGIMessage): Сообщение ASGI-приложения.
            """
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
            "headers": request_headers,
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

        Returns:
            ASGIResponse: Код состояния, заголовки и тело ответа.

        Raises:
            RuntimeError: Приложение не отправило ответ.
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
