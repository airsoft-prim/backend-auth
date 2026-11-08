from fastapi import status
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from loguru import logger

from src.domain.errors import (
    ApplicationError,
    JWTDecryptionError,
    JWTEncryptionError,
    ProviderError,
    SecurityError,
    SessionNotFoundError,
    UserAlreadyExistsError,
    UserAuthenticationError,
    UserAuthorizationError,
    UserIdentificationError,
)

from ._utils import ExceptionHandlersRegistrator, ExceptionsHandlingMap


async def unexpected_exc_handler(_: Request, exc: Exception) -> JSONResponse:
    """Возвращает ответ `500` для неожиданного исключения.

    Args:
        _ (Request): HTTP-запрос; обработчик его не использует.
        exc (Exception): Исключение, переданное обработчику `FastAPI`.

    Returns:
        JSONResponse: JSON-ответ с кодом `500` и описанием ошибки.
    """
    logger.opt(exception=exc).error("Unexpected error.")

    content = {
        "message": "Unexpected error.",
        "details": "Server completed processing the request with an unexpected error.",
    }

    return JSONResponse(content=content, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


async def uncought_exc_handler(_: Request, exc: ApplicationError) -> JSONResponse:
    """Возвращает ответ `422` для ошибки приложения без отдельного обработчика.

    Args:
        _ (Request): HTTP-запрос; обработчик его не использует.
        exc (ApplicationError): Исключение, переданное обработчику `FastAPI`.

    Returns:
        JSONResponse: JSON-ответ с кодом `422` и описанием ошибки.
    """
    logger.opt(exception=exc).warning("Unexpected error.")

    content = {
        "message": "Business logic error.",
        "details": "Server was unable to process the request due to a business rule violation.",
    }

    return JSONResponse(content=content, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)


async def provider_exc_handler(_: Request, exc: ProviderError) -> JSONResponse:
    """Возвращает ответ `500` при отказе внешнего ресурса.

    Args:
        _ (Request): HTTP-запрос; обработчик его не использует.
        exc (ProviderError): Исключение, переданное обработчику `FastAPI`.

    Returns:
        JSONResponse: JSON-ответ с кодом `500` и описанием ошибки.
    """
    logger.opt(exception=exc).error("Infrastructure request failed.")

    content = {
        "message": "Infrastructure error.",
        "details": "Server was unable to access a required resource.",
    }

    return JSONResponse(content=content, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


async def jwt_encryption_exc_handler(_: Request, exc: JWTEncryptionError) -> JSONResponse:
    """Возвращает ответ `500` при ошибке выпуска JWT.

    Args:
        _ (Request): HTTP-запрос; обработчик его не использует.
        exc (JWTEncryptionError): Исключение, переданное обработчику `FastAPI`.

    Returns:
        JSONResponse: JSON-ответ с кодом `500` и описанием ошибки.
    """
    logger.opt(exception=exc).error("Access token issuing failed.")

    content = {
        "message": "Token issuing error.",
        "details": "Server was unable to issue the token.",
    }

    return JSONResponse(
        content=content,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


async def jwt_decryption_exc_handler(_: Request, exc: JWTDecryptionError) -> JSONResponse:
    """Возвращает ответ `403` при ошибке проверки JWT.

    Args:
        _ (Request): HTTP-запрос; обработчик его не использует.
        exc (JWTDecryptionError): Исключение, переданное обработчику `FastAPI`.

    Returns:
        JSONResponse: JSON-ответ с кодом `403` и описанием ошибки.
    """
    logger.opt(exception=exc).info("Access token check failed.")

    content = {
        "message": "Authorization failed.",
        "details": "Provided credentials are invalid.",
    }

    return JSONResponse(content=content, status_code=status.HTTP_403_FORBIDDEN)


async def user_auth_exc_handler(_: Request, exc: UserAuthorizationError) -> JSONResponse:
    """Возвращает ответ `401` при отсутствии обязательного токена.

    Args:
        _ (Request): HTTP-запрос; обработчик его не использует.
        exc (UserAuthorizationError): Исключение, переданное обработчику `FastAPI`.

    Returns:
        JSONResponse: JSON-ответ с кодом `401` и описанием ошибки.
    """
    logger.opt(exception=exc).info("Bearer token is missing.")

    content = {
        "message": "Authorization failed.",
        "details": "Bearer token is missing.",
    }

    return JSONResponse(
        content=content,
        status_code=status.HTTP_401_UNAUTHORIZED,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def login_exc_handler(_: Request, exc: SecurityError) -> JSONResponse:
    """Возвращает одинаковый ответ `401` при ошибке логина или пароля.

    Args:
        _ (Request): HTTP-запрос; обработчик его не использует.
        exc (SecurityError): Исключение, переданное обработчику `FastAPI`.

    Returns:
        JSONResponse: JSON-ответ с кодом `401` и описанием ошибки.
    """
    exc_map: dict[type[SecurityError], int] = {
        UserIdentificationError: status.HTTP_401_UNAUTHORIZED,
        UserAuthenticationError: status.HTTP_401_UNAUTHORIZED,
    }

    content = {
        "message": "Authentication failed.",
        "details": "Provided credentials are invalid.",
    }

    headers = {"WWW-Authenticate": "Bearer"}

    return JSONResponse(content=content, status_code=exc_map[exc.__class__], headers=headers)


async def user_exists_exc_handler(_: Request, exc: UserAlreadyExistsError) -> JSONResponse:
    """Возвращает ответ `409` при занятости логина или почты.

    Args:
        _ (Request): HTTP-запрос; обработчик его не использует.
        exc (UserAlreadyExistsError): Исключение, переданное обработчику `FastAPI`.

    Returns:
        JSONResponse: JSON-ответ с кодом `409` и описанием ошибки.
    """
    logger.opt(exception=exc).debug("User with provided data already exists.")

    content = {
        "message": "User already exists",
        "details": str(exc),
    }

    return JSONResponse(content=content, status_code=status.HTTP_409_CONFLICT)


async def session_not_found_exc_handler(_: Request, exc: SessionNotFoundError) -> JSONResponse:
    """Возвращает ответ `404` для отсутствующей или чужой сессии.

    Args:
        _ (Request): HTTP-запрос; обработчик его не использует.
        exc (SessionNotFoundError): Исключение, переданное обработчику `FastAPI`.

    Returns:
        JSONResponse: JSON-ответ с кодом `404` и описанием ошибки.
    """
    logger.opt(exception=exc).debug("Session not found or not owned.")

    content = {
        "message": "Session not found.",
        "details": "The session does not exist or does not belong to the current user.",
    }

    return JSONResponse(content=content, status_code=status.HTTP_404_NOT_FOUND)


_handling_map: ExceptionsHandlingMap = {
    Exception: unexpected_exc_handler,
    ApplicationError: uncought_exc_handler,
    ProviderError: provider_exc_handler,
    JWTEncryptionError: jwt_encryption_exc_handler,
    JWTDecryptionError: jwt_decryption_exc_handler,
    UserIdentificationError: login_exc_handler,
    UserAuthenticationError: login_exc_handler,
    UserAuthorizationError: user_auth_exc_handler,
    UserAlreadyExistsError: user_exists_exc_handler,
    SessionNotFoundError: session_not_found_exc_handler,
}

register_exception_handlers = ExceptionHandlersRegistrator(_handling_map)
