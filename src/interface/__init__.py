"""HTTP-интерфейс сервиса аутентификации.

Объединяет маршруты учётных записей, сессий, паролей, проверок состояния и JWKS, `middleware` и
обработчики ошибок.

Преобразует HTTP-запросы в вызовы прикладных сценариев и собирает зависимости `FastAPI`.
"""

from fastapi import APIRouter

from .auth import router as auth_router
from .health import router as health_router
from .password import router as password_router
from .sessions import router as session_router
from .well_known import router as well_known_router

__all__ = ["main_router"]

main_router = APIRouter()

main_router.include_router(auth_router)
main_router.include_router(health_router)
main_router.include_router(password_router)
main_router.include_router(session_router)
main_router.include_router(well_known_router)
