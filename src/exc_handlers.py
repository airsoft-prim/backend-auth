from fastapi import status
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from loguru import logger

from src.general.exceptions import ApplicationError

from ._utils import ExceptionHandlersRegistrator, ExceptionsHandlingMap


async def unexpected_exc_handler(_: Request, exc: Exception) -> JSONResponse:
    """Любая неожиданная и/или неперехваченная ошибка транслируется данным обработчиком
    в 500 код ответа на запрос.
    """
    logger.opt(exception=exc).error("Unexpected serror.")

    content = {
        "message": "Unexpected error.",
        "details": "Server completed processing the request with an unexpected error.",
    }

    return JSONResponse(content=content, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


async def uncought_exc_handler(_: Request, exc: ApplicationError) -> JSONResponse:
    """Обработчик неотловленных доменных ошибок.

    Срабатывает на все ошибки доменной логики, если для них не существует
    спецефического обработчика.
    """
    logger.opt(exception=exc).warning("Unexpected serror.")

    content = {
        "message": "Business logic error.",
        "error_type": exc.__class__.__name__,
        "details": "Server was unable to process the request due to a business rule violation.",
    }

    return JSONResponse(content=content, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)


# TODO: Реализовать error handler для сервисных ошибок (UserAlreadyExistsError в частности.)

_handling_map: ExceptionsHandlingMap = {
    Exception: unexpected_exc_handler,
    ApplicationError: uncought_exc_handler,
}

register_exception_handlers = ExceptionHandlersRegistrator(_handling_map)
