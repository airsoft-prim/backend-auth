from collections.abc import Sequence
from datetime import UTC, datetime
import json
from string import Template
from typing import Any

from src.domain.entities import Session

from ._base import RedisRepository


class RedisSessionRepository(RedisRepository):
    """Репозиторий сессий пользователей в `Redis`.

    Сессия хранится в JSON по ключу `session:{sid}` с TTL до `expires_at`; сеты
    `session:user:{user_id}` индексируют сессии по владельцу для лимита активных сессий.
    """

    _key_template = Template("session:$sid")
    _user_index_template = Template("session:user:$user_id")

    async def save(self, session: Session) -> None:
        """Сохраняет сессию с TTL до её истечения.

        Args:
            session (Session): Сессия для сохранения.
        """
        ttl = int((session.expires_at - datetime.now(UTC)).total_seconds())

        if ttl <= 0:
            return

        key = self._key_template.substitute(sid=session.id)
        index = self._user_index_template.substitute(user_id=session.user_id)
        payload = self._serialize(session)

        with self._as_repository_error("Session saving error."):
            await self.client.set(key, payload, ex=ttl)
            await self.client.sadd(index, session.id)

    async def get(self, sid: str) -> Session | None:
        """Возвращает сессию по её `sid`.

        Args:
            sid (str): Идентификатор сессии.

        Returns:
            Session | None: Сессия или `None`, если её нет или срок истёк.
        """
        key = self._key_template.substitute(sid=sid)

        with self._as_repository_error("Session getting error."):
            payload = await self.client.get(key)

        return self._deserialize(sid, payload) if payload is not None else None

    async def list_active(self, user_id: int) -> Sequence[Session]:
        """Возвращает активные сессии пользователя.

        Args:
            user_id (int): Идентификатор владельца сессий.

        Returns:
            Sequence[Session]: Неотозванные и неистёкшие сессии пользователя.
        """
        index = self._user_index_template.substitute(user_id=user_id)

        with self._as_repository_error("Session listing error."):
            sids = [self._decode(sid) for sid in await self.client.smembers(index)]
            keys = [self._key_template.substitute(sid=sid) for sid in sids]
            payloads = await self.client.mget(keys)

        now = datetime.now(UTC)
        sessions: list[Session] = []

        for sid, payload in zip(sids, payloads, strict=True):
            if payload is None:
                continue

            session = self._deserialize(sid, payload)

            if session is not None and session.revoked_at is None and session.expires_at > now:
                sessions.append(session)

        return sessions

    @staticmethod
    def _serialize(session: Session) -> str:
        """Сериализует сессию в JSON.

        Args:
            session (Session): Сессия.

        Returns:
            str: JSON-представление сессии без `id` (он — часть ключа).
        """
        return json.dumps(
            {
                "user_id": session.user_id,
                "created_at": session.created_at.isoformat(),
                "expires_at": session.expires_at.isoformat(),
                "revoked_at": session.revoked_at.isoformat() if session.revoked_at else None,
                "ip": session.ip,
                "user_agent": session.user_agent,
                "platform": session.platform,
                "browser": session.browser,
                "location": session.location,
            }
        )

    @staticmethod
    def _decode(value: str | bytes) -> str:
        """Приводит значение `Redis` к строке.

        Args:
            value (str | bytes): Значение из `Redis`.

        Returns:
            str: Строковое значение.
        """
        return value if isinstance(value, str) else value.decode()

    @staticmethod
    def _deserialize(sid: str | bytes, payload: str | bytes) -> Session:
        """Восстанавливает сессию из JSON.

        Args:
            sid (str | bytes): Идентификатор сессии.
            payload (str | bytes): JSON-представление сессии.

        Returns:
            Session: Восстановленная сессия.
        """
        data: dict[str, Any] = json.loads(payload)

        return Session(
            id=sid if isinstance(sid, str) else sid.decode(),
            user_id=data["user_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            revoked_at=(
                datetime.fromisoformat(data["revoked_at"]) if data.get("revoked_at") else None
            ),
            ip=data.get("ip"),
            user_agent=data.get("user_agent"),
            platform=data.get("platform"),
            browser=data.get("browser"),
            location=data.get("location"),
        )
