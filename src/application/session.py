from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import uuid4

from src.domain.entities import Session
from src.domain.errors import SessionNotFoundError
from src.domain.ports import RevokedTokensRepository, SessionRepository

from ._base import AbstractUseCase

# Признаки платформ в User-Agent. Порядок важен: iOS-агенты содержат и "like Mac OS X",
# поэтому "iPhone"/"iPad" проверяются раньше macOS-признаков, а Android — раньше Linux.
_PLATFORM_MARKERS: Final[tuple[tuple[str, str], ...]] = (
    ("Windows", "Windows"),
    ("Android", "Android"),
    ("iPhone", "iOS"),
    ("iPad", "iPadOS"),
    ("CrOS", "ChromeOS"),
    ("Mac OS X", "macOS"),
    ("Macintosh", "macOS"),
    ("Linux", "Linux"),
)

# Признаки браузеров в User-Agent. Порядок важен: браузеры на движке Chromium
# (Edge, Opera, Yandex) содержат и "Chrome", поэтому проверяются раньше него.
_BROWSER_MARKERS: Final[tuple[tuple[str, str], ...]] = (
    ("YaBrowser", "Yandex"),
    ("Edg", "Edge"),
    ("OPR", "Opera"),
    ("Firefox", "Firefox"),
    ("Chrome", "Chrome"),
    ("Safari", "Safari"),
)


def parse_user_agent(user_agent: str) -> tuple[str | None, str | None]:
    """Разбирает User-Agent на платформу и браузер.

    Эвристика без внешних библиотек: ищет известные подстроки в порядке приоритета,
    поэтому результат не исчерпывающий, но достаточный для списка сессий.

    Args:
        user_agent (str): Строка заголовка `User-Agent`.

    Returns:
        tuple[str | None, str | None]: Пара (платформа, браузер) или None, если
            признак не найден.
    """
    platform = next((name for marker, name in _PLATFORM_MARKERS if marker in user_agent), None)
    browser = next((name for marker, name in _BROWSER_MARKERS if marker in user_agent), None)

    return platform, browser


class CreateSession(AbstractUseCase):
    """Use case создания сессии пользователя."""

    def __init__(self, sessions: SessionRepository, ttl: int, max_active: int) -> None:
        """Инициализация класса.

        Args:
            sessions (SessionRepository): Порт доступа к сессиям.
            ttl (int): Срок жизни сессии в секундах.
            max_active (int): Максимальное число активных сессий на пользователя.
        """
        self._sessions = sessions
        self._ttl = ttl
        self._max_active = max_active

    async def __call__(
        self, user_id: int, *, ip: str | None = None, user_agent: str | None = None
    ) -> Session:
        """Создаёт сессию, не превышая лимит активных сессий.

        Args:
            user_id (int): Идентификатор владельца сессии.
            ip (str | None, optional): IP-адрес входа. Defaults to None.
            user_agent (str | None, optional): Строка `User-Agent` входа. Defaults to None.

        Returns:
            Session: Созданная сессия.
        """
        active = list(await self._sessions.list_active(user_id))

        if len(active) >= self._max_active:
            oldest = min(active, key=lambda session: session.created_at)
            oldest.revoked_at = datetime.now(UTC)
            await self._sessions.save(oldest)

        now = datetime.now(UTC)
        platform, browser = parse_user_agent(user_agent) if user_agent is not None else (None, None)

        session = Session(
            id=uuid4().hex,
            user_id=user_id,
            created_at=now,
            expires_at=now + timedelta(seconds=self._ttl),
            ip=ip,
            user_agent=user_agent,
            platform=platform,
            browser=browser,
        )

        await self._sessions.save(session)

        return session


class SlideSession(AbstractUseCase):
    """Use case продления сессии (sliding expiration)."""

    def __init__(self, sessions: SessionRepository, ttl: int) -> None:
        """Инициализация класса.

        Args:
            sessions (SessionRepository): Порт доступа к сессиям.
            ttl (int): Срок жизни сессии в секундах.
        """
        self._sessions = sessions
        self._ttl = ttl

    async def __call__(self, sid: str) -> None:
        """Продлевает сессию на `ttl` от текущего момента.

        Args:
            sid (str): Идентификатор сессии.
        """
        session = await self._sessions.get(sid)

        if session is not None and session.revoked_at is None:
            session.expires_at = datetime.now(UTC) + timedelta(seconds=self._ttl)
            await self._sessions.save(session)


class ListSessions(AbstractUseCase):
    """Use case получения активных сессий пользователя."""

    def __init__(self, sessions: SessionRepository) -> None:
        """Инициализация класса.

        Args:
            sessions (SessionRepository): Порт доступа к сессиям.
        """
        self._sessions = sessions

    async def __call__(self, user_id: int) -> Sequence[Session]:
        """Возвращает активные сессии пользователя, от новых к старым.

        Args:
            user_id (int): Идентификатор владельца сессий.

        Returns:
            Sequence[Session]: Активные сессии пользователя.
        """
        sessions = await self._sessions.list_active(user_id)

        return sorted(sessions, key=lambda session: session.created_at, reverse=True)


class CloseSession(AbstractUseCase):
    """Use case закрытия одной сессии пользователя."""

    def __init__(self, tokens: RevokedTokensRepository, sessions: SessionRepository) -> None:
        """Инициализация класса.

        Args:
            tokens (RevokedTokensRepository): Порт доступа к отозванным сессиям.
            sessions (SessionRepository): Порт доступа к сессиям пользователей.
        """
        self._tokens = tokens
        self._sessions = sessions

    async def __call__(self, user_id: int, sid: str) -> None:
        """Отзывает сессию и её токены до конца срока действия.

        Args:
            user_id (int): Идентификатор владельца сессии.
            sid (str): Идентификатор сессии.

        Raises:
            SessionNotFoundError: Сессия не найдена или не принадлежит пользователю.
        """
        session = await self._sessions.get(sid)

        if session is None or session.user_id != user_id:
            msg = "Session not found."
            raise SessionNotFoundError(msg) from None

        if session.revoked_at is not None:
            return

        now = datetime.now(UTC)
        if (ttl := int((session.expires_at - now).total_seconds())) > 0:
            await self._tokens.store_session(sid, ttl)

        session.revoked_at = now
        await self._sessions.save(session)


class CloseOtherSessions(AbstractUseCase):
    """Use case закрытия всех сессий пользователя, кроме текущей."""

    def __init__(self, sessions: SessionRepository, close: CloseSession) -> None:
        """Инициализация класса.

        Args:
            sessions (SessionRepository): Порт доступа к сессиям пользователей.
            close (CloseSession): Use case закрытия отдельной сессии.
        """
        self._sessions = sessions
        self._close = close

    async def __call__(self, user_id: int, current_sid: str) -> None:
        """Закрывает все активные сессии пользователя, кроме текущей.

        Args:
            user_id (int): Идентификатор владельца сессий.
            current_sid (str): Идентификатор сессии, которую следует оставить.
        """
        for session in await self._sessions.list_active(user_id):
            if session.id != current_sid:
                await self._close(user_id, session.id)
