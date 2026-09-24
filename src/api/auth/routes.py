from typing import Any

from fastapi import APIRouter

from .docs import LOGIN_DOCS, LOGOUT_DOCS, REGISTER_DOCS
from .schemas import AccessToken, LoginRequestBody, RegisterRequestBody

router = APIRouter(prefix="/auth", tags=["Аутентификация"])


@router.post("/register", **REGISTER_DOCS)
async def register_user(body: RegisterRequestBody) -> None:
    """Функция регистрации нового пользователя.

    Args:
        body (RegisterRequestBody): Данные новой учётной записи.
    """
    raise NotImplementedError


@router.post("/login", **LOGIN_DOCS)
async def login_user(body: LoginRequestBody) -> AccessToken:
    """Функция входа в систему.

    Args:
        body (LoginRequestBody): Учётные данные пользователя.

    Returns:
        AccessToken: Данные сессии, включая токен доступа и его параметры.
    """
    raise NotImplementedError


@router.post("/logout", **LOGOUT_DOCS)
async def logout_user(current_user: Any) -> None:
    """Функция выхода из системы.

    Args:
        current_user (Any): Пользователь, которому принадлежит токен.
    """
    raise NotImplementedError
