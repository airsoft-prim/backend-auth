from string import Template

from src.domain.enums import TokenType

from ._base import RedisRepository


# TODO: перерабатывается — в сессионной модели инвалидация идёт через сессию, а не по
# отдельному токену; отзыв по `jti` пока остаётся только для ротации refresh-токена.
class RedisRevokedTokensRepository(RedisRepository):
    """Репозиторий отозванных токенов в Redis."""

    _key_template = Template("token:$type:revoked:$jti")

    async def store(self, token_type: TokenType, token_id: str, ttl: int) -> None:
        """Помечает токен отозванным до истечения его срока действия.

        Args:
            token_type (TokenType): Тип токена (`access` или `refresh`).
            token_id (str): Идентификатор токена (`jti`).
            ttl (int): Оставшееся время жизни токена в секундах.

        Raises:
            RepositoryError: Если обращение к Redis завершилось ошибкой.
        """
        key = self.compile_template({"type": token_type.value, "jti": token_id})

        with self._as_repository_error("Revoked token saving error."):
            await self.client.set(key, "1", ex=ttl)

    async def check(self, token_type: TokenType, token_id: str) -> bool:
        """Проверяет, отозван ли токен.

        Args:
            token_type (TokenType): Тип токена (`access` или `refresh`).
            token_id (str): Идентификатор токена (`jti`).

        Raises:
            RepositoryError: Если обращение к Redis завершилось ошибкой.

        Returns:
            bool: True, если токен помечен отозванным.
        """
        key = self.compile_template({"type": token_type.value, "jti": token_id})

        with self._as_repository_error("Revoked token getting error."):
            return bool(await self.client.exists(key))
