from typing import Annotated

from fastapi import APIRouter, Body, Depends, Response

from src.application.auth import UserService
from src.application.token import JWTEncryptionService, TokenRevocationService
from src.domain.entities import AccessTokenClaims, User

from .deps import (
    get_access_token,
    get_current_user,
    get_encryption_service,
    get_token_revocation_service,
    get_user_service,
)
from .docs import LOGIN_DOCS, LOGOUT_DOCS, ME_DOCS, REGISTER_DOCS
from .schemas import AccessToken, LoginRequestBody, RegisterRequestBody, UserData

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


@router.get("/me", **ME_DOCS)
async def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> UserData:
    """Функция получения данных учётной записи владельца токена.

    Args:
        current_user (User): Учётная запись владельца проверенного токена.

    Returns:
        UserData: Данные учётной записи без служебных полей.
    """
    return UserData.model_validate(current_user)


@router.post("/logout", response_class=Response, **LOGOUT_DOCS)
async def logout_user(
    claims: Annotated[AccessTokenClaims, Depends(get_access_token)],
    revocation_service: Annotated[TokenRevocationService, Depends(get_token_revocation_service)],
) -> None:
    """Функция выхода из системы.

    Args:
        claims (AccessTokenClaims): Проверенные claims токена текущей сессии.
        revocation_service (TokenRevocationService): Сервис отзыва токенов.
    """
    await revocation_service.revoke(claims)
