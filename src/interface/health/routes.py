from fastapi import APIRouter, status
from fastapi.responses import PlainTextResponse
from loguru import logger
from redis import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.adapters.cache import create_client
from src.adapters.database import engine

from .docs import LIVENESS_DOCS, READINESS_DOCS

router = APIRouter(prefix="/health", tags=["Состояние приложения"])


@router.get("/liveness", **LIVENESS_DOCS)
async def liveness_healthcheck() -> PlainTextResponse:
    """Подтверждает доступность HTTP-процесса без проверки хранилищ.

    Returns:
        PlainTextResponse: Пустой ответ `204`.
    """
    logger.success("Application healthy.")

    return PlainTextResponse(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/readiness", **READINESS_DOCS)
async def readiness_healthcheck() -> PlainTextResponse:
    """Проверяет готовность PostgreSQL и `Redis` к запросам.

    Последовательно выполняет SELECT `1` и `Redis` PING. При ошибке любой проверки возвращает
    `503`; при успешных проверках — `204`.

    Returns:
        PlainTextResponse: Пустой ответ `204` или `503`.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    except SQLAlchemyError, Exception:  # noqa: BLE001
        logger.critical("Database is unavailable.")
        return PlainTextResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    try:
        async with create_client() as client:
            await client.ping()

    except RedisError, Exception:  # noqa: BLE001
        logger.critical("Cache is unavailable.")
        return PlainTextResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    logger.success("Application ready.")
    return PlainTextResponse(status_code=status.HTTP_204_NO_CONTENT)
