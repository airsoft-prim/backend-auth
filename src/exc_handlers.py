from fastapi import status
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from loguru import logger

from src.general.exceptions import ApplicationError, ProviderError, SecurityError
from src.services.jwt import JWTDecryptionError, JWTEncryptionError
from src.services.user import (
    UserAlreadyExistsError,
    UserAuthenticationError,
    UserIdentificationError,
)

from ._utils import ExceptionHandlersRegistrator, ExceptionsHandlingMap


async def unexpected_exc_handler(_: Request, exc: Exception) -> JSONResponse:
    """Любая неожиданная и/или неперехваченная ошибка транслируется данным обработчиком
    в 500 код ответа на запрос.
    """
    logger.opt(exception=exc).error("Unexpected error.")

    content = {
        "message": "Unexpected error.",
        "details": "Server completed processing the request with an unexpected error.",
    }

    return JSONResponse(content=content, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


async def uncought_exc_handler(_: Request, exc: ApplicationError) -> JSONResponse:
    """Обработчик неотловленных доменных ошибок.

    Срабатывает на все ошибки доменной логики, если для них не существует
    специфического обработчика.
    """
    logger.opt(exception=exc).warning("Unexpected error.")

    content = {
        "message": "Business logic error.",
        "details": "Server was unable to process the request due to a business rule violation.",
    }

    return JSONResponse(content=content, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)


async def provider_exc_handler(_: Request, exc: ProviderError) -> JSONResponse:
    """Обработчик отказов внешних ресурсов.

    Ошибки БД, кеша и файловой системы — отказ инфраструктуры, а не нарушение
    бизнес-правила, поэтому клиент получает 500, а не 422.
    """
    logger.opt(exception=exc).error("Infrastructure request failed.")

    content = {
        "message": "Infrastructure error.",
        "details": "Server was unable to access a required resource.",
    }

    return JSONResponse(content=content, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


async def jwt_encryption_exc_handler(_: Request, exc: JWTEncryptionError) -> JSONResponse:
    """Обработчик ошибок безопасности, связанных с выпуском JWT-токена.

    Проблема при выпуске токена.
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
    """Обработчик ошибок безопасности, связанных с проверкой JWT-токена.

    Невалидный, просроченный или неподписанный токен.
    """
    logger.opt(exception=exc).info("Access token check failed.")

    content = {
        "message": "Authorization failed.",
        "details": "Provided credentials are invalid.",
    }

    return JSONResponse(content=content, status_code=status.HTTP_403_FORBIDDEN)


async def login_exc_handler(_: Request, exc: SecurityError) -> JSONResponse:
    """Обработчик ошибок, возникающих во время процедуры login пользователя."""
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

    logger.opt(exception=exc).debug("User with provided data already exists.")

    content = {
        "message": "User already exists",
        "details": str(exc),
    }

    return JSONResponse(content=content, status_code=status.HTTP_409_CONFLICT)


_handling_map: ExceptionsHandlingMap = {
    Exception: unexpected_exc_handler,
    ApplicationError: uncought_exc_handler,
    ProviderError: provider_exc_handler,
    JWTEncryptionError: jwt_encryption_exc_handler,
    JWTDecryptionError: jwt_decryption_exc_handler,
    UserIdentificationError: login_exc_handler,
    UserAuthenticationError: login_exc_handler,
    UserAlreadyExistsError: user_exists_exc_handler,
}

register_exception_handlers = ExceptionHandlersRegistrator(_handling_map)
