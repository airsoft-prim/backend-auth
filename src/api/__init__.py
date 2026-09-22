from fastapi import APIRouter

from .health import router as health_router

main_router = APIRouter()

main_router.include_router(health_router)

__all__ = ["main_router"]
