from pwdlib import PasswordHash

from src.general.exceptions import SecurityError, ServiceError
from src.providers.database.models import User
from src.providers.database.repositories import UserRepository


class UserAlreadyExistsError(ServiceError):
    """Ошибка регистрации: учётная запись с таким username или email уже есть."""


class UserIdentificationError(SecurityError):
    """Ошибка идентификации пользователя."""


class UserAuthenticationError(SecurityError):
    """Ошибка аутентификации пользователя."""


class UserService:
    """Сервис учётных записей портала."""

    def __init__(self, user_repository: UserRepository, hasher: PasswordHash) -> None:
        """Инициализация класса.

        Args:
            user_repository (UserRepository): Репозиторий учётных записей.
            hasher (PasswordHash): Хешер паролей (argon2, `pwdlib[argon2]`).
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

        return user.id, user.system_role
