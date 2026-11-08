from src.domain.entities import User
from src.domain.errors import (
    UserAlreadyExistsError,
    UserAuthenticationError,
    UserIdentificationError,
)
from src.domain.ports import PasswordHasher, UserRepository

from ._base import AbstractUseCase


class RegisterUser(AbstractUseCase):
    """Use case регистрации учётной записи портала.

    Проверяет занятость логина и адреса почты через `UserRepository`, хеширует пароль через
    `PasswordHasher` и сохраняет новую учётную запись.
    """

    def __init__(self, users: UserRepository, hasher: PasswordHasher) -> None:
        """Инициализация класса.

        Args:
            users (UserRepository): Порт доступа к учётным записям.
            hasher (PasswordHasher): Порт хеширования паролей (argon2, `pwdlib[argon2]`).
        """
        self._users = users
        self._hasher = hasher

    async def __call__(self, username: str, email: str, password: str) -> None:
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


class LoginUser(AbstractUseCase):
    """Use case входа пользователя в систему.

    Находит учётную запись по логину, отклоняет отсутствующую или заблокированную запись и
    проверяет пароль. Возвращает идентификатор и роль; сессию и токены не создаёт.
    """

    def __init__(self, users: UserRepository, hasher: PasswordHasher) -> None:
        """Инициализация класса.

        Args:
            users (UserRepository): Порт доступа к учётным записям.
            hasher (PasswordHasher): Порт хеширования паролей (argon2, `pwdlib[argon2]`).
        """
        self._users = users
        self._hasher = hasher

    async def __call__(self, username: str, password: str) -> tuple[int, str]:
        """Выполняет вход пользователя в систему.

        Args:
            username (str): Имя пользователя.
            password (str): Пароль пользователя.

        Returns:
            tuple[int, str]: Идентификатор пользователя и его системная роль.

        Raises:
            UserIdentificationError: Учётная запись отсутствует, заблокирована или не имеет ID.
            UserAuthenticationError: Неверный пароль.
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


class GetUser(AbstractUseCase):
    """Use case получения учётной записи по её идентификатору.

    Загружает доменную сущность через `UserRepository`. Отсутствие записи преобразует в
    `UserIdentificationError`.
    """

    def __init__(self, users: UserRepository) -> None:
        """Инициализация класса.

        Args:
            users (UserRepository): Порт доступа к учётным записям.
        """
        self._users = users

    async def __call__(self, user_id: int) -> User:
        """Возвращает учётную запись по её идентификатору.

        Args:
            user_id (int): Идентификатор учётной записи.

        Returns:
            User: Найденная учётная запись.

        Raises:
            UserIdentificationError: Учётная запись не найдена.
        """
        user = await self._users.get(user_id)

        if user is None:
            msg = "User not found."
            raise UserIdentificationError(msg) from None

        return user
