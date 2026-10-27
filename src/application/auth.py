from src.domain.entities import AccessTokenClaims, User
from src.domain.errors import (
    UserAlreadyExistsError,
    UserAuthenticationError,
    UserAuthorizationError,
    UserIdentificationError,
)
from src.domain.ports import PasswordHasher, UserRepository

from .token import JWTDecryptionService, TokenRevocationService


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


class UserService:
    """Сервис учётных записей портала."""

    def __init__(self, user_repository: UserRepository, hasher: PasswordHasher) -> None:
        """Инициализация класса.

        Args:
            user_repository (UserRepository): Репозиторий учётных записей.
            hasher (PasswordHasher): Хешер паролей (argon2, `pwdlib[argon2]`).
        """
        self._users = user_repository
        self._hasher = hasher

    async def register(self, username: str, email: str, password: str) -> None:
        """Регистрирует учётную запись портала.

        Пароль приходит в открытом виде и сохраняется только в виде Argon2id-хеша.

        Args:
            username (str): Логин учётной записи.
            email (str): Адрес электронной почты — контакт для связи.
            password (str): Пароль учётной записи.

        Raises:
            UserAlreadyExistsError: Логин или адрес уже заняты.
        """
        if await self._users.get_by_username(username) is not None:
            msg = "Username is already taken."
            raise UserAlreadyExistsError(msg) from None

        if await self._users.get_by_email(email) is not None:
            msg = "Email is already taken."
            raise UserAlreadyExistsError(msg) from None

        pswd = self._hasher.hash(password)
        user = User(username=username, email=email, pswd_hash=pswd)

        await self._users.save(user)

    async def get_account(self, user_id: int) -> User:
        """Возвращает учётную запись по её идентификатору.

        Args:
            user_id (int): Идентификатор учётной записи.

        Raises:
            UserIdentificationError: Учётная запись не найдена.

        Returns:
            User: Найденная учётная запись.
        """
        user = await self._users.get(user_id)

        if user is None:
            msg = "User not found."
            raise UserIdentificationError(msg) from None

        return user

    async def login(self, username: str, password: str) -> tuple[int, str]:
        """Выполняет вход пользователя в систему.

        Args:
            username (str): Имя пользователя.
            password (str): Пароль пользователя.

        Raises:
            UserIdentificationError: Пользователь не найден.
            UserAuthenticationError: Неверный пароль.

        Returns:
            tuple[int, str]: Идентификатор пользователя и его системная роль.
        """
        user = await self._users.get_by_username(username)
        if user is None or user.disabled:
            msg = "User not found."
            raise UserIdentificationError(msg) from None

        if not self._hasher.verify(password, user.pswd_hash):
            msg = "Password is incorrect."
            raise UserAuthenticationError(msg) from None

        if user.id is None:
            msg = "Stored account has no identifier."
            raise UserIdentificationError(msg) from None

        return user.id, user.system_role
