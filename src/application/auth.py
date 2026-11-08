from src.application.session import CreateSession
from src.application.token import IssueTokenPair, RotateRefreshToken, SignToken, TokenPair
from src.domain.entities import User
from src.domain.errors import (
    UserAlreadyExistsError,
    UserAuthenticationError,
    UserIdentificationError,
)
from src.domain.ports import PasswordHasher, UserRepository
from src.domain.tokens import RefreshTokenClaims

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


class OpenUserSession:
    """Открывает сессию пользователя после проверки учётных данных.

    Создаёт запись сессии с контекстом устройства и выпускает связанный с ней refresh-токен.
    """

    def __init__(
        self, users: UserRepository, hasher: PasswordHasher, session: CreateSession, sign: SignToken
    ) -> None:
        """Инициализация класса.

        Args:
            users (UserRepository): Порт доступа к учётным записям.
            hasher (PasswordHasher): Порт проверки пароля.
            session (CreateSession): Сценарий создания сессии.
            sign (SignToken): Сценарий подписи refresh-токена.
        """
        self._users = users
        self._hasher = hasher
        self._session = session
        self._sign = sign

    async def __call__(
        self, username: str, password: str, *, ip: str | None = None, user_agent: str | None = None
    ) -> str:
        """Проверяет учётные данные и возвращает refresh-токен новой сессии.

        Args:
            username (str): Имя пользователя.
            password (str): Пароль в открытом виде.
            ip (str | None): IP-адрес входа или `None`, если он неизвестен.
            user_agent (str | None): Заголовок `User-Agent` или `None`, если он отсутствует.

        Returns:
            str: Подписанный refresh-токен созданной сессии.

        Raises:
            UserIdentificationError: Учётная запись отсутствует, заблокирована или не имеет ID.
            UserAuthenticationError: Пароль не соответствует сохранённому хешу.
        """
        user = await self._users.get_by_username(username)

        if user is None or user.disabled:
            msg = "User not found."
            raise UserIdentificationError(msg) from None

        if user.id is None:  # Проверка, диктуемая доменным ограничением
            msg = "Stored account has no identifier."
            raise UserIdentificationError(msg) from None

        if not self._hasher.verify(password, user.pswd_hash):
            msg = "Password is incorrect."
            raise UserAuthenticationError(msg) from None

        session = await self._session(user.id, ip=ip, user_agent=user_agent)
        token, _ = await self._sign(user.id, session.id)

        return token


class RefreshUserSession:
    """Обновляет токены активной сессии.

    Загружает текущую роль владельца, ротирует предъявленный refresh-токен и выпускает новую
    пару токенов для той же сессии.
    """

    def __init__(self, rotate: RotateRefreshToken, users: GetUser, issue: IssueTokenPair) -> None:
        """Инициализация класса.

        Args:
            rotate (RotateRefreshToken): Сценарий ротации refresh-токена и продления сессии.
            users (GetUser): Сценарий получения учётной записи владельца.
            issue (IssueTokenPair): Сценарий выпуска пары токенов.
        """
        self._rotate = rotate
        self._users = users
        self._issue = issue

    async def __call__(self, claims: RefreshTokenClaims) -> TokenPair:
        """Возвращает новую пару токенов после ротации refresh-токена.

        Args:
            claims (RefreshTokenClaims): Проверенные claims предъявленного refresh-токена.

        Returns:
            TokenPair: Access- и refresh-токены сессии и срок жизни access-токена в секундах.
        """
        user = await self._users(int(claims["sub"]))

        await self._rotate(claims)

        return await self._issue(claims["sub"], claims["sid"], user.system_role)
