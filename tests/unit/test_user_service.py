"""Тесты сервиса учётных записей."""

from pwdlib import PasswordHash
import pytest

from src.general.enums import UserRole
from src.providers.database.models import User
from src.services.user import (
    UserAlreadyExistsError,
    UserAuthenticationError,
    UserIdentificationError,
    UserService,
)
from tests.doubles import InMemoryUserRepository, as_user_repository

USERNAME = "stalker_2010"
EMAIL = "user@airsoft-prim.ru"
PASSWORD = "Str0ng!Pass"  # noqa: S105
USER_ID = 42


@pytest.fixture
def repository() -> InMemoryUserRepository:
    """Отдаёт пустую подмену репозитория учётных записей.

    Returns:
        InMemoryUserRepository: Хранилище учётных записей в памяти.
    """
    return InMemoryUserRepository()


@pytest.fixture
def service(repository: InMemoryUserRepository, password_hash: PasswordHash) -> UserService:
    """Отдаёт сервис учётных записей поверх подмены репозитория.

    Args:
        repository (InMemoryUserRepository): Подмена репозитория.
        password_hash (PasswordHash): Хешер паролей приложения.

    Returns:
        UserService: Сервис учётных записей.
    """
    return UserService(
        user_repository=as_user_repository(repository),
        hasher=password_hash,
    )


def _stored_account(
    username: str = USERNAME,
    email: str = EMAIL,
    *,
    pswd_hash: str = "stored-hash",
    role: UserRole = UserRole.USER,
    disabled: bool = False,
) -> User:
    """Собирает учётную запись, которая уже есть в хранилище.

    Args:
        username (str): Логин хранимой учётной записи.
        email (str): Адрес хранимой учётной записи.
        pswd_hash (str, optional): Хеш пароля учётной записи. Defaults to "stored-hash".
        role (UserRole, optional): Системная роль учётной записи. Defaults to `UserRole.USER`.
        disabled (bool, optional): Признак блокировки. Defaults to False.

    Returns:
        User: Учётная запись с хешем-заглушкой: пароль хранимой записи тест не проверяет.
    """
    account = User(
        username=username,
        email=email,
        pswd_hash=pswd_hash,
        system_role=role,
        disabled=disabled,
    )
    account.id = USER_ID

    return account


async def test_register_stores_account_with_hashed_password(
    service: UserService,
    repository: InMemoryUserRepository,
    password_hash: PasswordHash,
) -> None:
    """Регистрация новой учётной записи.

    Given: логин и адрес свободны,
    When: гость регистрируется с паролем по политике,
    Then: учётная запись сохранена, а пароль лежит только в виде Argon2id-хеша.
    """
    # Когда
    await service.register(username=USERNAME, email=EMAIL, password=PASSWORD)

    # Тогда
    assert len(repository.users) == 1

    account = repository.users[0]
    assert account.username == USERNAME
    assert account.email == EMAIL
    assert account.pswd_hash != PASSWORD
    assert account.pswd_hash.startswith("$argon2id$")
    assert password_hash.verify(PASSWORD, account.pswd_hash)


async def test_register_rejects_login_that_is_taken(
    service: UserService,
    repository: InMemoryUserRepository,
) -> None:
    """Занятый логин.

    Given: логин уже зарегистрирован,
    When: гость регистрируется с тем же логином,
    Then: сервис отказывает и не сохраняет вторую учётную запись.
    """
    # Дано
    repository.users.append(_stored_account())

    # Когда / Тогда
    with pytest.raises(UserAlreadyExistsError, match=r"Username is already taken\."):
        await service.register(username=USERNAME, email="other@airsoft-prim.ru", password=PASSWORD)

    assert len(repository.users) == 1


async def test_register_rejects_email_that_is_taken_in_any_case(
    service: UserService,
    repository: InMemoryUserRepository,
) -> None:
    """Занятый адрес в другом регистре.

    Given: адрес уже зарегистрирован в нижнем регистре,
    When: гость регистрируется с тем же адресом в верхнем регистре,
    Then: сервис отказывает: адреса сравниваются без учёта регистра.
    """
    # Дано
    repository.users.append(_stored_account())

    # Когда / Тогда
    with pytest.raises(UserAlreadyExistsError, match=r"Email is already taken\."):
        await service.register(username="another_2010", email=EMAIL.upper(), password=PASSWORD)

    assert len(repository.users) == 1


async def test_register_keeps_logins_case_sensitive(
    service: UserService,
    repository: InMemoryUserRepository,
) -> None:
    """Логин в другом регистре.

    Given: занят логин `Stalker_2010`,
    When: гость регистрируется с логином `stalker_2010`,
    Then: регистрация проходит: логины уникальны регистрозависимо.
    """
    # Дано
    repository.users.append(
        _stored_account(username="Stalker_2010", email="stored@airsoft-prim.ru")
    )

    # Когда
    await service.register(username=USERNAME, email=EMAIL, password=PASSWORD)

    # Тогда
    assert [account.username for account in repository.users] == ["Stalker_2010", USERNAME]


async def test_login_returns_user_id_and_role(
    service: UserService,
    repository: InMemoryUserRepository,
    password_hash: PasswordHash,
) -> None:
    """Успешный вход.

    Given: учётная запись с паролем и ролью `moderator`,
    When: пользователь входит с верными данными,
    Then: сервис возвращает Id пользователя и его системную роль.
    """
    # Дано
    repository.users.append(
        _stored_account(
            pswd_hash=password_hash.hash(PASSWORD),
            role=UserRole.MODERATOR,
        )
    )

    # Когда
    subject, role = await service.login(USERNAME, PASSWORD)

    # Тогда
    assert subject == USER_ID
    assert role == UserRole.MODERATOR


async def test_login_rejects_unknown_user(service: UserService) -> None:
    """Вход с несуществующим логином.

    Given: учётной записи с таким логином нет,
    When: пользователь пытается войти,
    Then: сервис сообщает об ошибке идентификации.
    """
    # Когда / Тогда
    with pytest.raises(UserIdentificationError, match="User not found"):
        await service.login(USERNAME, PASSWORD)


async def test_login_rejects_wrong_password(
    service: UserService,
    repository: InMemoryUserRepository,
    password_hash: PasswordHash,
) -> None:
    """Вход с неверным паролем.

    Given: учётная запись существует, но пароль не совпадает,
    When: пользователь пытается войти,
    Then: сервис сообщает об ошибке аутентификации.
    """
    # Дано
    repository.users.append(_stored_account(pswd_hash=password_hash.hash(PASSWORD)))

    # Когда / Тогда
    with pytest.raises(UserAuthenticationError, match="Password is incorrect"):
        await service.login(USERNAME, "Wrong1!Pass")


async def test_login_rejects_disabled_user(
    service: UserService,
    repository: InMemoryUserRepository,
    password_hash: PasswordHash,
) -> None:
    """Вход заблокированного пользователя.

    Given: учётная запись заблокирована, а пароль верный,
    When: пользователь пытается войти,
    Then: сервис не раскрывает блокировку и отвечает как на несуществующий логин.
    """
    # Дано
    repository.users.append(
        _stored_account(
            pswd_hash=password_hash.hash(PASSWORD),
            disabled=True,
        )
    )

    # Когда / Тогда
    with pytest.raises(UserIdentificationError, match="User not found"):
        await service.login(USERNAME, PASSWORD)
