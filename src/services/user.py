from pwdlib import PasswordHash

from src.general.exceptions import ServiceError
from src.providers.database.models import User
from src.providers.database.repositories import UserRepository


class UserAlreadyExistsError(ServiceError):
    """Ошибка регистрации: учётная запись с таким username или email уже есть."""


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

    async def register(self, *, username: str, email: str, password: str) -> None:
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
