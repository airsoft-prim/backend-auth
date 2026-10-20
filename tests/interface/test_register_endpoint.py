"""Тесты HTTP-контракта регистрации учётной записи."""

from fastapi import status
import pytest

from src.general.exceptions import RepositoryError
from src.services.user import UserAlreadyExistsError
from tests.interface.conftest import RegisterClientFactory, StubUserService

REGISTER_PATH = "/auth/register"
USERNAME = "stalker_2010"
EMAIL = "user@airsoft-prim.ru"
PASSWORD = "Str0ng!Pass"  # noqa: S105
# 52 символа, но 76 байт: проверка «не длиннее 72 байт» была ограничением bcrypt.
MULTIBYTE_PASSWORD = "Parol1!ПпПпПп" * 4


def _body(**overrides: str) -> dict[str, str]:
    """Собирает тело запроса на регистрацию.

    Args:
        **overrides (str): Поля, которые тест заменяет.

    Returns:
        dict[str, str]: Тело запроса на регистрацию.
    """
    return {"username": USERNAME, "email": EMAIL, "password": PASSWORD} | overrides


async def test_register_creates_account_without_body(
    register_client_factory: RegisterClientFactory,
) -> None:
    """Регистрация новой учётной записи.

    Given: логин и адрес свободны,
    When: гость отправляет данные регистрации,
    Then: приходит 204 без тела: профиль созданной учётной записи не отдаётся
    (`docs/API_AUTH.md` §4.1).
    """
    # Дано
    service = StubUserService()
    client = register_client_factory(service)

    # Когда
    response = await client.post(REGISTER_PATH, payload=_body())

    # Тогда
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.body == b""
    assert "content-type" not in response.headers
    assert service.received == {"username": USERNAME, "email": EMAIL, "password": PASSWORD}


async def test_register_accepts_password_longer_than_72_bytes(
    register_client_factory: RegisterClientFactory,
) -> None:
    """Пароль длиннее 72 байт.

    Given: пароль укладывается в 72 символа, но занимает больше 72 байт,
    When: гость регистрируется,
    Then: приходит 204: предел в 72 байта был ограничением bcrypt, а Argon2id его не имеет.
    """
    # Дано
    service = StubUserService()
    client = register_client_factory(service)

    # Когда
    response = await client.post(REGISTER_PATH, payload=_body(password=MULTIBYTE_PASSWORD))

    # Тогда
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert service.received is not None
    assert service.received["password"] == MULTIBYTE_PASSWORD


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("password", "weakpassword"),
        ("password", "Aa1!" * 19),
        ("username", "ab"),
        ("username", "1stalker"),
        ("email", "not-an-email"),
    ],
)
async def test_register_rejects_body_that_breaks_the_policy(
    register_client_factory: RegisterClientFactory,
    field: str,
    value: str,
) -> None:
    """Тело, не отвечающее политике регистрации.

    Given: одно из полей тела не отвечает политике username, email или пароля,
    When: гость отправляет данные регистрации,
    Then: приходит 422, а до сервиса учётных записей запрос не доходит.
    """
    # Дано
    service = StubUserService()
    client = register_client_factory(service)

    # Когда
    response = await client.post(REGISTER_PATH, payload=_body(**{field: value}))

    # Тогда
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert service.received is None


@pytest.mark.parametrize(
    "message",
    ["Username is already taken.", "Email is already taken."],
)
async def test_register_fails_with_conflict_when_credentials_are_taken(
    register_client_factory: RegisterClientFactory,
    message: str,
) -> None:
    """Занятые учётные данные.

    Given: логин или адрес уже зарегистрированы,
    When: гость регистрируется с теми же данными,
    Then: приходит 409 с причиной из сервиса (`docs/API_AUTH.md` §4.1).
    """
    # Дано
    service = StubUserService(error=UserAlreadyExistsError(message))
    client = register_client_factory(service)

    # Когда
    response = await client.post(REGISTER_PATH, payload=_body())

    # Тогда
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.payload == {"message": "User already exists", "details": message}


async def test_register_fails_with_server_error_when_database_is_unavailable(
    register_client_factory: RegisterClientFactory,
) -> None:
    """Отказ БД.

    Given: обращения к БД завершаются ошибкой,
    When: гость отправляет данные регистрации,
    Then: приходит 500: отказ инфраструктуры не выдаётся за занятые учётные данные.
    """
    # Дано
    service = StubUserService(error=RepositoryError("User saving error."))
    client = register_client_factory(service)

    # Когда
    response = await client.post(REGISTER_PATH, payload=_body())

    # Тогда
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
