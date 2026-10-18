from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Final

from fastapi import FastAPI
from loguru import logger

from src.api import main_router
from src.core.configs import config
from src.rotation import get_rotation_daemon

from .exc_handlers import register_exception_handlers
from .middlewares import register_middlewares

APP_DESCRIPTION: Final[str] = """
Сервер аутентификации для портала Airsoft-Prim.
"""


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    """Lifespan приложения FastAPI."""
    logger.info("Application starting up...")

    get_rotation_daemon().start()
    logger.success("JWK Rotation Daemon started.")

    logger.success("Application started.")
    logger.info(f"Debug mode is {'OOFNF'[config.app.DEBUG :: 2]}.")

    yield

    logger.warning("Application is shutting down.")


application = FastAPI(
    title=config.app.NAME,
    description=APP_DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
)

register_exception_handlers(application)
register_middlewares(application)

application.include_router(main_router)
