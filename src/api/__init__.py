from fastapi import APIRouter

from .health import router as health_router
from .well_known import router as well_known_router

main_router = APIRouter()

main_router.include_router(health_router)
main_router.include_router(well_known_router)

__all__ = ["main_router"]
