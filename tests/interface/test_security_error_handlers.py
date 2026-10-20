"""Тесты HTTP-контракта ошибок безопасности."""

from fastapi import FastAPI, status
import pytest

from src.exc_handlers import register_exception_handlers
from src.general.exceptions import SecurityError
from src.services.jwt import JWTDecryptionError, JWTEncryptionError
from src.services.user import UserAuthenticationError
from tests.asgi_client import ASGIClient

DECRYPTION_PATH = "/test/jwt-decrypt"
ENCRYPTION_PATH = "/test/jwt-encrypt"
LOGIN_PATH = "/test/login"
SECURITY_PATH = "/test/security"
ENCRYPTION_DETAILS = "Signing key file is missing."


@pytest.fixture
def security_client() -> ASGIClient:
    """Отдаёт клиент приложения с маршрутами, поднимающими ошибки безопасности.

    Обработчики регистрируются теми же средствами, что и в приложении, поэтому тест
    проверяет и сам обработчик, и выбор обработчика по типу исключения.

    Returns:
        ASGIClient: Клиент тестового приложения.
    """
    app = FastAPI()
    register_exception_handlers(app)

    @app.get(DECRYPTION_PATH)
    async def _raise_decryption_error() -> None:
        msg = "Token is invalid."
        raise JWTDecryptionError(msg)

    @app.get(ENCRYPTION_PATH)
    async def _raise_encryption_error() -> None:
        raise JWTEncryptionError(ENCRYPTION_DETAILS)

    @app.get(LOGIN_PATH)
    async def _raise_login_error() -> None:
        msg = "Password is incorrect."
        raise UserAuthenticationError(msg)

    @app.get(SECURITY_PATH)
    async def _raise_security_error() -> None:
        msg = "Access denied."
        raise SecurityError(msg)

    return ASGIClient(app)


async def test_jwt_decryption_error_returns_forbidden(
    security_client: ASGIClient,
) -> None:
    """Невалидный токен.

    Given: проверка токена завершилась ошибкой `JWTDecryptionError`,
    When: исключение доходит до обработчика приложения,
    Then: клиент получает 403 с телом `message`/`details` без `error_type`.
    """
    # Когда
    response = await security_client.get(DECRYPTION_PATH)

    # Тогда
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "www-authenticate" not in response.headers
    assert response.payload == {
        "message": "Authorization failed.",
        "details": "Provided credentials are invalid.",
    }


async def test_login_error_returns_unauthorized_with_challenge(
    security_client: ASGIClient,
) -> None:
    """Неверный пароль.

    Given: вход завершился ошибкой `UserAuthenticationError`,
    When: исключение доходит до обработчика приложения,
    Then: клиент получает 401 с `WWW-Authenticate: Bearer` и общим телом ошибки.
    """
    # Когда
    response = await security_client.get(LOGIN_PATH)

    # Тогда
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.payload == {
        "message": "Authentication failed.",
        "details": "Provided credentials are invalid.",
    }


async def test_security_error_without_specific_handler_returns_domain_error(
    security_client: ASGIClient,
) -> None:
    """Ошибка безопасности без отдельного обработчика.

    Given: поднята неспециализированная `SecurityError`,
    When: исключение доходит до общего обработчика доменных ошибок,
    Then: клиент получает 422, как и для любой другой доменной ошибки.
    """
    # Когда
    response = await security_client.get(SECURITY_PATH)

    # Тогда
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "www-authenticate" not in response.headers
    assert response.payload["message"] == "Business logic error."


async def test_jwt_encryption_error_returns_server_error_without_details(
    security_client: ASGIClient,
) -> None:
    """Отказ выпуска токена.

    Given: поднять `JWTEncryptionError` с причиной отказа keyfile,
    When: исключение доходит до обработчика приложения,
    Then: клиент получает 500 без внутренней причины и без `error_type`.
    """
    # Когда
    response = await security_client.get(ENCRYPTION_PATH)

    # Тогда
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.payload == {
        "message": "Token issuing error.",
        "details": "Server was unable to issue the token.",
    }
    assert ENCRYPTION_DETAILS not in response.body.decode()
    assert "www-authenticate" not in response.headers
