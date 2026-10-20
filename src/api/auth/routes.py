from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Response

from src.services import JWTEncryptionService
from src.services.user import UserService

from .deps import get_encryption_service, get_user_service
from .docs import LOGIN_DOCS, LOGOUT_DOCS, REGISTER_DOCS
from .schemas import AccessToken, LoginRequestBody, RegisterRequestBody

router = APIRouter(prefix="/auth", tags=["Аутентификация"])


@router.post("/register", response_class=Response, **REGISTER_DOCS)
async def register_user(
    body: Annotated[RegisterRequestBody, Body(...)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> None:
    """Функция регистрации нового пользователя.

    Args:
        body (RegisterRequestBody): Данные новой учётной записи.
        service (UserService): Сервис учётных записей.
    """

    await service.register(
        username=body.username,
        email=body.email,
        password=body.password.get_secret_value(),
    )


@router.post("/login", **LOGIN_DOCS)
async def login_user(
    body: Annotated[LoginRequestBody, Body(...)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    token_service: Annotated[JWTEncryptionService, Depends(get_encryption_service)],
) -> AccessToken:
    """Функция входа в систему.

    Args:
        body (LoginRequestBody): Учётные данные пользователя.

    Returns:
        AccessToken: Данные сессии, включая токен доступа и его параметры.
    """
    subject, role = await user_service.login(body.username, body.password.get_secret_value())
    access_token, expires_in = await token_service.encrypt(subject, role)

    return AccessToken(access_token=access_token, expires_in=expires_in)


@router.post("/logout", **LOGOUT_DOCS)
async def logout_user(current_user: Any) -> None:
    """Функция выхода из системы.

    Args:
        current_user (Any): Пользователь, которому принадлежит токен.
    """
    raise NotImplementedError
