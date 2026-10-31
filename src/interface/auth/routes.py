from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, Response

from src.application.auth import LoginUser, RegisterUser
from src.application.token import RevokeToken, SignToken
from src.domain.entities import User
from src.domain.tokens import AccessTokenClaims

from .deps import (
    get_access_token,
    get_current_user,
    get_login_user,
    get_register_user,
    get_revoke_token,
    get_sign_token,
)
from .docs import LOGIN_DOCS, LOGOUT_DOCS, ME_DOCS, REGISTER_DOCS
from .schemas import AccessToken, LoginRequestBody, RegisterRequestBody, UserData

router = APIRouter(prefix="/auth", tags=["Аутентификация"])


@router.post("/register", response_class=Response, **REGISTER_DOCS)
async def register_user(
    body: Annotated[RegisterRequestBody, Body(...)],
    register: Annotated[RegisterUser, Depends(get_register_user)],
) -> None:
    """Функция регистрации нового пользователя.

    Args:
        body (RegisterRequestBody): Данные новой учётной записи.
        register (RegisterUser): Use case регистрации.
    """
    await register(
        username=body.username,
        email=body.email,
        password=body.password.get_secret_value(),
    )


@router.post("/login", **LOGIN_DOCS)
async def login_user(
    body: Annotated[LoginRequestBody, Body(...)],
    login: Annotated[LoginUser, Depends(get_login_user)],
    sign_token: Annotated[SignToken, Depends(get_sign_token)],
) -> AccessToken:
    """Функция входа в систему.

    Args:
        body (LoginRequestBody): Учётные данные пользователя.
        login (LoginUser): Use case входа.
        sign_token (SignToken): Use case подписи токена.

    Returns:
        AccessToken: Данные сессии, включая токен доступа и его параметры.
    """
    subject, role = await login(body.username, body.password.get_secret_value())
    access_token, expires_in = await sign_token(subject, uuid4().hex, not_required={"srl": role})

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
    revoke: Annotated[RevokeToken, Depends(get_revoke_token)],
) -> None:
    """Функция выхода из системы.

    Args:
        claims (AccessTokenClaims): Проверенные claims токена текущей сессии.
        revoke (RevokeToken): Use case отзыва токена.
    """
    await revoke(claims)
