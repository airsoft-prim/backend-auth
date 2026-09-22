from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Final

from fastapi import FastAPI
from loguru import logger

from src.api import main_router
from src.core.configs import config

APP_DESCRIPTION: Final[str] = """
Сервер аутентификации для портала Airsoft-Prim.
"""


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    """Lifespan приложения FastAPI."""

    logger.info("Application starting up...")
    logger.info(f"Debug mode is {'OOFNF'[config.app.DEBUG :: 2]}.")

    yield

    logger.warning("Application is shutting down.")


application = FastAPI(
    title=config.app.NAME,
    description=APP_DESCRIPTION,
    version="0.1.0",
    lifespan=lifespan,
)

application.include_router(main_router)
