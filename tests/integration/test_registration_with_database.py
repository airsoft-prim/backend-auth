"""Тесты регистрации учётной записи поверх настоящей БД."""

from pwdlib import PasswordHash
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.database.repositories import SqlAlchemyUserRepository
from src.application.auth import UserService
from src.domain.entities import User
from src.domain.enums import UserRole
from src.domain.errors import RepositoryError, UserAlreadyExistsError

USERNAME = "stalker_2010"
EMAIL = "user@airsoft-prim.ru"
PASSWORD = "Str0ng!Pass"  # noqa: S105


@pytest.fixture
def service(database_session: AsyncSession, password_hash: PasswordHash) -> UserService:
    """Отдаёт сервис учётных записей поверх настоящего репозитория.

    Args:
        database_session (AsyncSession): Сессия БД теста.
        password_hash (PasswordHash): Хешер паролей приложения.

    Returns:
        UserService: Сервис, работающий с настоящей БД.
    """
    return UserService(
        user_repository=SqlAlchemyUserRepository(database_session),
        hasher=password_hash,
    )


async def test_registration_stores_hashed_account_in_database(
    service: UserService,
    database_session: AsyncSession,
    password_hash: PasswordHash,
) -> None:
    """Регистрация новой учётной записи.

    Given: логин и адрес свободны, таблицы схемы `auth` на месте,
    When: гость регистрируется,
    Then: учётная запись записана с Argon2id-хешем пароля, ролью `user` и метками времени,
    а пароль проверяется по сохранённому хешу.
    """
    # Когда
    await service.register(username=USERNAME, email=EMAIL, password=PASSWORD)

    # Тогда
    stored = await SqlAlchemyUserRepository(database_session).get_by_username(USERNAME)
    assert stored is not None
    assert stored.id is not None
    assert stored.system_role is UserRole.USER
    assert stored.email == EMAIL
    assert stored.pswd_hash != PASSWORD
    assert stored.pswd_hash.startswith("$argon2id$")
    assert password_hash.verify(PASSWORD, stored.pswd_hash)
    assert stored.created_at is not None
    assert stored.updated_at is not None
    assert stored.created_at.tzinfo is not None
    assert stored.updated_at.tzinfo is not None


async def test_registration_rejects_taken_credentials(service: UserService) -> None:
    """Повторная регистрация.

    Given: учётная запись уже зарегистрирована,
    When: гость регистрируется с тем же логином или с тем же адресом в другом регистре,
    Then: сервис отказывает по каждому поводу.
    """
    # Дано
    await service.register(username=USERNAME, email=EMAIL, password=PASSWORD)

    # Когда / Тогда
    with pytest.raises(UserAlreadyExistsError, match=r"Username is already taken\."):
        await service.register(username=USERNAME, email="other@airsoft-prim.ru", password=PASSWORD)

    with pytest.raises(UserAlreadyExistsError, match=r"Email is already taken\."):
        await service.register(username="another_2010", email=EMAIL.upper(), password=PASSWORD)


async def test_database_keeps_email_unique_regardless_of_case(
    database_session: AsyncSession,
) -> None:
    """Уникальность адреса в БД.

    Given: в БД есть учётная запись с адресом в нижнем регистре,
    When: мимо сервисной проверки сохраняется тот же адрес в верхнем регистре,
    Then: БД отвергает запись: уникальность держит функциональный индекс по `lower(email)`.
    """
    # Дано
    repository = SqlAlchemyUserRepository(database_session)
    await repository.save(User(username=USERNAME, email=EMAIL, pswd_hash="stored-hash"))

    # Когда / Тогда
    with pytest.raises(RepositoryError):
        await repository.save(
            User(username="another_2010", email=EMAIL.upper(), pswd_hash="stored-hash")
        )
