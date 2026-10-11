"""Тесты сервиса учётных записей."""

from pwdlib import PasswordHash
import pytest

from src.providers.database.models import User
from src.services.user import UserAlreadyExistsError, UserService
from tests.doubles import InMemoryUserRepository, as_user_repository

USERNAME = "stalker_2010"
EMAIL = "user@airsoft-prim.ru"
PASSWORD = "Str0ng!Pass"  # noqa: S105


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


def _stored_account(username: str = USERNAME, email: str = EMAIL) -> User:
    """Собирает учётную запись, которая уже есть в хранилище.

    Args:
        username (str): Логин хранимой учётной записи.
        email (str): Адрес хранимой учётной записи.

    Returns:
        User: Учётная запись с хешем-заглушкой: пароль хранимой записи тест не проверяет.
    """
    return User(username=username, email=email, pswd_hash="stored-hash")


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
