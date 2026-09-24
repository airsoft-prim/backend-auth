from fastapi import APIRouter, status
from fastapi.responses import PlainTextResponse
from loguru import logger
from redis import RedisError
from redis.asyncio import Connection
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.providers.cache import connection_pool
from src.providers.database import engine

from .docs import LIVENESS_DOCS, READINESS_DOCS

router = APIRouter(prefix="/health", tags=["Состояние приложения"])


@router.get("/liveness", **LIVENESS_DOCS)
async def liveness_healthcheck() -> PlainTextResponse:
    """Функция проверки доступности приложения.

    Returns:
        PlainTextResponse: Пустой ответ без тела.
    """
    logger.success("Application healthy.")

    return PlainTextResponse(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/readiness", **READINESS_DOCS)
async def readiness_healthcheck() -> PlainTextResponse:
    """Функция проверки готовности приложения.

    Returns:
        PlainTextResponse: Пустой ответ без тела.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    except SQLAlchemyError, Exception:  # noqa: BLE001
        logger.critical("Database is unavailable.")
        return PlainTextResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    try:
        conn: Connection = await connection_pool.get_connection()
        await connection_pool.release(conn)

    except RedisError, Exception:  # noqa: BLE001
        logger.critical("Cache is unavailable.")
        return PlainTextResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    logger.success("Application ready.")
    return PlainTextResponse(status_code=status.HTTP_204_NO_CONTENT)
