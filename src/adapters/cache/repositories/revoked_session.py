from string import Template

from ._base import RedisRepository


class RedisRevokedSessionsRepository(RedisRepository):
    """Репозиторий отозванных сессий в `Redis`.

    Отозванная сессия хранится по ключу `session:revoked:<sid>` с TTL до истечения её `refresh`-
    токена; проверка токенов сверяется с этим ключом по `sid`.
    """

    _key_template = Template("session:revoked:$sid")

    async def store(self, sid: str, ttl: int) -> None:
        """Помечает сессию отозванной до истечения срока её действия.

        Args:
            sid (str): Идентификатор сессии.
            ttl (int): Оставшееся время жизни сессии в секундах.
        """
        key = self._key_template.substitute(sid=sid)

        with self._as_repository_error("Revoked session saving error."):
            await self.client.set(key, "1", ex=ttl)

    async def check(self, sid: str) -> bool:
        """Проверяет, отозвана ли сессия.

        Args:
            sid (str): Идентификатор сессии.

        Returns:
            bool: `True`, если сессия помечена отозванной.
        """
        key = self._key_template.substitute(sid=sid)

        with self._as_repository_error("Revoked session getting error."):
            return bool(await self.client.exists(key))
