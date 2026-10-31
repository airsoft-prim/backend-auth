from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Final

from fastapi import FastAPI
from loguru import logger

from src.bootstrap import get_rotation_daemon
from src.config import config
from src.interface import main_router
from src.interface.exc_handlers import register_exception_handlers
from src.interface.middlewares import register_middlewares

from ._version import __version__

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
    lifespan=lifespan,
    title=f"{config.app.PROJECT} | {config.app.NAME}",
    description=APP_DESCRIPTION,
    version=__version__,
)

register_exception_handlers(application)
register_middlewares(application)

application.include_router(main_router)
