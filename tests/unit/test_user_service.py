"""Тесты сервиса учётных записей."""

from pwdlib import PasswordHash
import pytest

from src.application.auth import GetUser, LoginUser, RegisterUser
from src.domain.entities import User
from src.domain.enums import UserRole
from src.domain.errors import (
    UserAlreadyExistsError,
    UserAuthenticationError,
    UserIdentificationError,
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
def register_user(
    repository: InMemoryUserRepository,
    password_hash: PasswordHash,
) -> RegisterUser:
    """Отдаёт use case регистрации поверх подмены репозитория.

    Args:
        repository (InMemoryUserRepository): Подмена репозитория.
        password_hash (PasswordHash): Хешер паролей приложения.

    Returns:
        RegisterUser: Use case регистрации учётной записи.
    """
    return RegisterUser(users=as_user_repository(repository), hasher=password_hash)


@pytest.fixture
def login_user(repository: InMemoryUserRepository, password_hash: PasswordHash) -> LoginUser:
    """Отдаёт use case входа поверх подмены репозитория.

    Args:
        repository (InMemoryUserRepository): Подмена репозитория.
        password_hash (PasswordHash): Хешер паролей приложения.

    Returns:
        LoginUser: Use case входа пользователя.
    """
    return LoginUser(users=as_user_repository(repository), hasher=password_hash)


@pytest.fixture
def get_user(repository: InMemoryUserRepository) -> GetUser:
    """Отдаёт use case получения учётной записи поверх подмены репозитория.

    Args:
        repository (InMemoryUserRepository): Подмена репозитория.

    Returns:
        GetUser: Use case получения учётной записи.
    """
    return GetUser(users=as_user_repository(repository))


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
        pswd_hash (str): Хеш пароля учётной записи.
        role (UserRole): Системная роль учётной записи.
        disabled (bool): Признак блокировки.

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
    register_user: RegisterUser,
    repository: InMemoryUserRepository,
    password_hash: PasswordHash,
) -> None:
    """Регистрация новой учётной записи.

    Given: логин и адрес свободны, When: гость регистрируется с паролем по политике, Then: учётная
    запись сохранена, а пароль лежит только в виде Argon2id-хеша.

    Args:
        register_user (RegisterUser): Сценарий регистрации через репозиторий текущего теста.
        repository (InMemoryUserRepository): Репозиторий публичных JWK для подмены зависимости.
        password_hash (PasswordHash): Хешер паролей Argon2, используемый приложением.
    """
    # Когда
    await register_user(username=USERNAME, email=EMAIL, password=PASSWORD)

    # Тогда
    assert len(repository.users) == 1

    account = repository.users[0]
    assert account.username == USERNAME
    assert account.email == EMAIL
    assert account.pswd_hash != PASSWORD
    assert account.pswd_hash.startswith("$argon2id$")
    assert password_hash.verify(PASSWORD, account.pswd_hash)


async def test_register_rejects_login_that_is_taken(
    register_user: RegisterUser,
    repository: InMemoryUserRepository,
) -> None:
    """Занятый логин.

    Given: логин уже зарегистрирован, When: гость регистрируется с тем же логином, Then: сервис
    отказывает и не сохраняет вторую учётную запись.

    Args:
        register_user (RegisterUser): Сценарий регистрации через репозиторий текущего теста.
        repository (InMemoryUserRepository): Репозиторий публичных JWK для подмены зависимости.
    """
    # Дано
    repository.users.append(_stored_account())

    # Когда / Тогда
    with pytest.raises(UserAlreadyExistsError, match=r"Username is already taken\."):
        await register_user(username=USERNAME, email="other@airsoft-prim.ru", password=PASSWORD)

    assert len(repository.users) == 1


async def test_register_rejects_email_that_is_taken_in_any_case(
    register_user: RegisterUser,
    repository: InMemoryUserRepository,
) -> None:
    """Занятый адрес в другом регистре.

    Given: адрес уже зарегистрирован в нижнем регистре, When: гость регистрируется с тем же адресом
    в верхнем регистре, Then: сервис отказывает: адреса сравниваются без учёта регистра.

    Args:
        register_user (RegisterUser): Сценарий регистрации через репозиторий текущего теста.
        repository (InMemoryUserRepository): Репозиторий публичных JWK для подмены зависимости.
    """
    # Дано
    repository.users.append(_stored_account())

    # Когда / Тогда
    with pytest.raises(UserAlreadyExistsError, match=r"Email is already taken\."):
        await register_user(username="another_2010", email=EMAIL.upper(), password=PASSWORD)

    assert len(repository.users) == 1


async def test_register_keeps_logins_case_sensitive(
    register_user: RegisterUser,
    repository: InMemoryUserRepository,
) -> None:
    """Логин в другом регистре.

    Given: занят логин `Stalker_2010`, When: гость регистрируется с логином `stalker_2010`, Then:
    регистрация проходит: логины уникальны регистрозависимо.

    Args:
        register_user (RegisterUser): Сценарий регистрации через репозиторий текущего теста.
        repository (InMemoryUserRepository): Репозиторий публичных JWK для подмены зависимости.
    """
    # Дано
    repository.users.append(
        _stored_account(username="Stalker_2010", email="stored@airsoft-prim.ru")
    )

    # Когда
    await register_user(username=USERNAME, email=EMAIL, password=PASSWORD)

    # Тогда
    assert [account.username for account in repository.users] == ["Stalker_2010", USERNAME]


async def test_get_account_returns_stored_user(
    get_user: GetUser,
    repository: InMemoryUserRepository,
) -> None:
    """Получение учётной записи по идентификатору.

    Given: учётная запись сохранена в репозитории, When: сервис запрашивает её по Id из токена,
    Then: возвращается та же учётная запись.

    Args:
        get_user (GetUser): Сценарий чтения учётной записи через тестовый репозиторий.
        repository (InMemoryUserRepository): Репозиторий публичных JWK для подмены зависимости.
    """
    # Дано
    account = _stored_account()
    repository.users.append(account)

    # Когда
    found = await get_user(USER_ID)

    # Тогда
    assert found is account


async def test_get_account_rejects_unknown_user(get_user: GetUser) -> None:
    """Получение несуществующей учётной записи.

    Given: учётной записи с таким Id нет в репозитории, When: сервис запрашивает её по Id из
    токена, Then: сервис сообщает об ошибке идентификации.

    Args:
        get_user (GetUser): Сценарий чтения учётной записи через тестовый репозиторий.
    """
    # Когда / Тогда
    with pytest.raises(UserIdentificationError, match="User not found"):
        await get_user(USER_ID)


async def test_login_returns_user_id_and_role(
    login_user: LoginUser,
    repository: InMemoryUserRepository,
    password_hash: PasswordHash,
) -> None:
    """Успешный вход.

    Given: учётная запись с паролем и ролью `moderator`, When: пользователь входит с верными
    данными, Then: сервис возвращает Id пользователя и его системную роль.

    Args:
        login_user (LoginUser): Сценарий входа через тестовый репозиторий учётных записей.
        repository (InMemoryUserRepository): Репозиторий публичных JWK для подмены зависимости.
        password_hash (PasswordHash): Хешер паролей Argon2, используемый приложением.
    """
    # Дано
    repository.users.append(
        _stored_account(
            pswd_hash=password_hash.hash(PASSWORD),
            role=UserRole.MODERATOR,
        )
    )

    # Когда
    subject, role = await login_user(USERNAME, PASSWORD)

    # Тогда
    assert subject == USER_ID
    assert role == UserRole.MODERATOR


async def test_login_rejects_unknown_user(login_user: LoginUser) -> None:
    """Вход с несуществующим логином.

    Given: учётной записи с таким логином нет, When: пользователь пытается войти, Then: сервис
    сообщает об ошибке идентификации.

    Args:
        login_user (LoginUser): Сценарий входа через тестовый репозиторий учётных записей.
    """
    # Когда / Тогда
    with pytest.raises(UserIdentificationError, match="User not found"):
        await login_user(USERNAME, PASSWORD)


async def test_login_rejects_wrong_password(
    login_user: LoginUser,
    repository: InMemoryUserRepository,
    password_hash: PasswordHash,
) -> None:
    """Вход с неверным паролем.

    Given: учётная запись существует, но пароль не совпадает, When: пользователь пытается войти,
    Then: сервис сообщает об ошибке аутентификации.

    Args:
        login_user (LoginUser): Сценарий входа через тестовый репозиторий учётных записей.
        repository (InMemoryUserRepository): Репозиторий публичных JWK для подмены зависимости.
        password_hash (PasswordHash): Хешер паролей Argon2, используемый приложением.
    """
    # Дано
    repository.users.append(_stored_account(pswd_hash=password_hash.hash(PASSWORD)))

    # Когда / Тогда
    with pytest.raises(UserAuthenticationError, match="Password is incorrect"):
        await login_user(USERNAME, "Wrong1!Pass")


async def test_login_rejects_disabled_user(
    login_user: LoginUser,
    repository: InMemoryUserRepository,
    password_hash: PasswordHash,
) -> None:
    """Вход заблокированного пользователя.

    Given: учётная запись заблокирована, а пароль верный, When: пользователь пытается войти, Then:
    сервис не раскрывает блокировку и отвечает как на несуществующий логин.

    Args:
        login_user (LoginUser): Сценарий входа через тестовый репозиторий учётных записей.
        repository (InMemoryUserRepository): Репозиторий публичных JWK для подмены зависимости.
        password_hash (PasswordHash): Хешер паролей Argon2, используемый приложением.
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
        await login_user(USERNAME, PASSWORD)
