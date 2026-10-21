from datetime import UTC, datetime

from src.general.enums import TokenType
from src.general.security import AccessTokenClaims
from src.providers.cache.repositories import RevokedTokensRepository
from src.services.jwt import JWTDecryptionError


class TokenRevokedError(JWTDecryptionError):
    """Ошибка проверки отозванного токена."""


class TokenRevocationService:
    """Сервис отзыва выданных токенов и проверки отзыва при аутентификации."""

    def __init__(self, repository: RevokedTokensRepository) -> None:
        """Инициализация класса.

        Args:
            repository (RevokedTokensRepository): Репозиторий отозванных токенов.
        """
        self._repository = repository

    async def ensure_active(
        self, claims: AccessTokenClaims, token_type: TokenType = TokenType.ACCESS
    ) -> None:
        """Проверяет, что токен не отозван.

        Args:
            claims (AccessTokenClaims): Проверенные claims токена.
            token_type (TokenType, optional): Тип токена. Defaults to TokenType.ACCESS.

        Raises:
            TokenRevokedError: Токен уже помечен отозванным.
        """
        if await self._repository.check(token_type, claims["jti"]):
            msg = "Token is revoked."
            raise TokenRevokedError(msg) from None

    async def revoke(
        self, claims: AccessTokenClaims, token_type: TokenType = TokenType.ACCESS
    ) -> None:
        """Помечает токен отозванным до истечения его срока действия.

        Запись в Redis получает TTL, равный остатку срока жизни токена. Если токен уже
        истёк, запись не создаётся: проверять его отзыв больше не нужно.

        Args:
            claims (AccessTokenClaims): Проверенные claims токена.
            token_type (TokenType, optional): Тип токена. Defaults to TokenType.ACCESS.
        """
        if (ttl := claims["exp"] - int(datetime.now(UTC).timestamp())) <= 0:
            return

        await self._repository.store(token_type, claims["jti"], ttl)
