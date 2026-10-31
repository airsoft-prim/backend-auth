from datetime import UTC, datetime, timedelta
from uuid import uuid4

from src.domain.entities import Session
from src.domain.ports import SessionRepository

from ._base import AbstractUseCase


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

    async def __call__(self, user_id: int) -> Session:
        """Создаёт сессию, не превышая лимит активных сессий.

        Args:
            user_id (int): Идентификатор владельца сессии.

        Returns:
            Session: Созданная сессия.
        """
        active = list(await self._sessions.list_active(user_id))

        if len(active) >= self._max_active:
            oldest = min(active, key=lambda session: session.created_at)
            oldest.revoked_at = datetime.now(UTC)
            await self._sessions.save(oldest)

        now = datetime.now(UTC)
        session = Session(
            id=uuid4().hex,
            user_id=user_id,
            created_at=now,
            expires_at=now + timedelta(seconds=self._ttl),
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
