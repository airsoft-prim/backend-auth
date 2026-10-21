from src.general.exceptions import SecurityError
from src.general.security import AccessTokenClaims
from src.services.jwt import JWTDecryptionService
from src.services.token import TokenRevocationService

__all__ = ["AuthorizationService", "UserAuthorizationError"]


class UserAuthorizationError(SecurityError):
    """Ошибка авторизации: в запросе нет Bearer-токена."""


class AuthorizationService:
    """Сервис авторизации запроса по Bearer-токену."""

    def __init__(
        self, decryption_service: JWTDecryptionService, revocation_service: TokenRevocationService
    ) -> None:
        """Инициализация класса.

        Args:
            decryption_service (JWTDecryptionService): Сервис проверки JWT токенов.
            revocation_service (TokenRevocationService): Сервис проверки отзыва токенов.
        """
        self._decryption = decryption_service
        self._revocation = revocation_service

    async def authorize(self, token: str | None) -> AccessTokenClaims:
        """Проверяет Bearer-токен и возвращает его claims.

        Args:
            token (str | None): Токен из заголовка `Authorization` или None, если
                заголовок отсутствует.

        Raises:
            UserAuthorizationError: Токен не передан.
            JWTDecryptionError: Токен недействителен, просрочен или уже отозван.

        Returns:
            AccessTokenClaims: Проверенные claims токена.
        """
        if token is None:
            msg = "Bearer token is missing."
            raise UserAuthorizationError(msg)

        claims = await self._decryption.decrypt(token)
        await self._revocation.ensure_active(claims)

        return claims
