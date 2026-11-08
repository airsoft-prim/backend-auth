from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import ClassVar
from uuid import uuid4

from src.domain.entities import Session
from src.domain.errors import JWTDecryptionError, SessionNotFoundError
from src.domain.ports import RevokedSessionsRepository, SessionRepository
from src.domain.tokens import RefreshTokenClaims

from ._base import AbstractUseCase


class RequireActiveSession(AbstractUseCase):
    """Проверяет принадлежность refresh-токена действующей сессии.

    Загружает сессию по `sid` и сверяет её владельца, срок действия и состояние отзыва.
    """

    def __init__(self, sessions: SessionRepository) -> None:
        """Инициализация класса.

        Args:
            sessions (SessionRepository): Порт доступа к сессиям.
        """
        self._sessions = sessions

    async def __call__(self, claims: RefreshTokenClaims) -> None:
        """Проверяет сессию владельца токена.

        Args:
            claims (RefreshTokenClaims): Проверенные данные refresh-токена с `sub` и `sid`.

        Raises:
            JWTDecryptionError: Субъект не является числом, сессия отсутствует, принадлежит
                другому пользователю, отозвана или истекла.
        """
        try:
            user_id = int(claims["sub"])

        except (TypeError, ValueError) as error:
            msg = "Token subject is invalid."
            raise JWTDecryptionError(msg) from error

        session = await self._sessions.get(claims["sid"])

        owned = session is not None and session.user_id == user_id
        revoked = session is not None and session.revoked_at is not None
        expired = session is not None and session.expires_at <= datetime.now(UTC)

        if not (owned and not revoked and not expired):
            msg = "Session is not active."
            raise JWTDecryptionError(msg) from None


class CreateSession(AbstractUseCase):
    """Use case создания сессии пользователя.

    При достижении лимита помечает самую старую активную сессию отозванной, затем сохраняет новую
    сессию с `UUID` и сроком жизни `ttl`. Контекст входа дополняется платформой и браузером из
    `User-Agent`.
    """

    # Признаки платформ в User-Agent. Порядок важен: iOS-агенты содержат и "like Mac OS X",
    # поэтому "iPhone"/"iPad" проверяются раньше macOS-признаков, а Android — раньше Linux.
    PLATFORM_MARKERS: ClassVar[tuple[tuple[str, str], ...]] = (
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
    BROWSER_MARKERS: ClassVar[tuple[tuple[str, str], ...]] = (
        ("YaBrowser", "Yandex"),
        ("Edg", "Edge"),
        ("OPR", "Opera"),
        ("Firefox", "Firefox"),
        ("Chrome", "Chrome"),
        ("Safari", "Safari"),
    )

    @classmethod
    def parse_user_agent(cls, user_agent: str) -> tuple[str | None, str | None]:
        """Разбирает `User-Agent` на платформу и браузер.

        Эвристика без внешних библиотек: ищет известные подстроки в порядке приоритета, поэтому
        результат не исчерпывающий, но достаточный для списка сессий.

        Args:
            user_agent (str): Строка заголовка `User-Agent`.

        Returns:
            tuple[str | None, str | None]: Пара (платформа, браузер) или `None`,
                если признак не найден.
        """
        _ = (name for marker, name in cls.PLATFORM_MARKERS if marker in user_agent)
        platform = next(_, None)

        _ = (name for marker, name in cls.BROWSER_MARKERS if marker in user_agent)
        browser = next(_, None)

        return platform, browser

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
            ip (str | None): IP-адрес входа.
            user_agent (str | None): Строка `User-Agent` входа.

        Returns:
            Session: Созданная сессия.
        """
        active = list(await self._sessions.list_active(user_id))

        if len(active) >= self._max_active:
            oldest = min(active, key=lambda session: session.created_at)
            oldest.revoked_at = datetime.now(UTC)

            await self._sessions.save(oldest)

        now = datetime.now(UTC)

        platform, browser = None, None
        if user_agent is not None:
            platform, browser = self.parse_user_agent(user_agent)

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


class ListSessions(AbstractUseCase):
    """Use case получения активных сессий пользователя.

    Получает активные сессии через `SessionRepository` и сортирует их по `created_at` от новых к
    старым.
    """

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
    """Use case закрытия одной сессии пользователя.

    Проверяет принадлежность сессии пользователю, сохраняет маркер отзыва на остаток срока её
    действия и устанавливает `revoked_at`. Повторное закрытие отозванной сессии ничего не меняет.
    """

    def __init__(self, revoked: RevokedSessionsRepository, sessions: SessionRepository) -> None:
        """Инициализация класса.

        Args:
            revoked (RevokedSessionsRepository): Порт доступа к отозванным сессиям.
            sessions (SessionRepository): Порт доступа к сессиям пользователей.
        """
        self._revoked = revoked
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
            await self._revoked.store(sid, ttl)

        session.revoked_at = now
        await self._sessions.save(session)

    async def others(self, user_id: int, current_sid: str) -> None:
        """Закрывает все активные сессии владельца, кроме текущей.

        Args:
            user_id (int): Идентификатор владельца сессий.
            current_sid (str): Идентификатор сессии, которую нужно сохранить.
        """
        for session in await self._sessions.list_active(user_id):
            if session.id != current_sid:
                await self(user_id, session.id)
