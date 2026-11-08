from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request, Response

from src.application.auth import OpenUserSession, RefreshUserSession, RegisterUser
from src.application.token import REFRESH_TOKEN_COOKIE, RevokeSession
from src.config import config
from src.domain.entities import User
from src.domain.tokens import RefreshTokenClaims

from .deps import (
    get_current_user,
    get_open_user_session,
    get_refresh_claims,
    get_refresh_token,
    get_refresh_user_session,
    get_register_user,
    get_revoke_session,
)
from .docs import LOGIN_DOCS, LOGOUT_DOCS, ME_DOCS, REFRESH_DOCS, REGISTER_DOCS
from .schemas import AccessToken, LoginRequestBody, RegisterRequestBody, UserData

router = APIRouter(prefix="/auth", tags=["Аутентификация"])


@router.post("/register", response_class=Response, **REGISTER_DOCS)
async def register_user(
    body: Annotated[RegisterRequestBody, Body(...)],
    register: Annotated[RegisterUser, Depends(get_register_user)],
) -> None:
    """Регистрирует учётную запись по данным запроса.

    Args:
        body (RegisterRequestBody): Данные новой учётной записи.
        register (RegisterUser): Use case регистрации.
    """
    await register(
        username=body.username,
        email=body.email,
        password=body.password.get_secret_value(),
    )


@router.post("/login", response_class=Response, **LOGIN_DOCS)
async def login_user(
    response: Response,
    request: Request,
    body: Annotated[LoginRequestBody, Body(...)],
    open_session: Annotated[OpenUserSession, Depends(get_open_user_session)],
) -> None:
    """Открывает сессию и записывает `refresh`-токен в cookie.

    Args:
        response (Response): Ответ, в который кладётся `refresh`-токен (cookie).
        request (Request): Запрос, из которого читается контекст входа (IP и `User-Agent`).
        body (LoginRequestBody): Учётные данные пользователя.
        open_session (OpenUserSession): Сценарий открытия сессии.
    """
    ip = request.client.host if request.client is not None else None
    refresh_token = await open_session(
        body.username,
        body.password.get_secret_value(),
        ip=ip,
        user_agent=request.headers.get("user-agent"),
    )

    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=refresh_token,
        max_age=config.security.REFRESH_TOKEN_TTL,
        httponly=True,
        secure=not config.app.DEBUG,
        samesite="lax",
    )


@router.get("/me", **ME_DOCS)
async def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> UserData:
    """Возвращает профиль владельца проверенного токена.

    Args:
        current_user (User): Учётная запись владельца проверенного токена.

    Returns:
        UserData: Данные учётной записи без служебных полей.
    """
    return UserData.model_validate(current_user)


@router.post("/refresh", **REFRESH_DOCS)
async def refresh_access_token(
    response: Response,
    claims: Annotated[RefreshTokenClaims, Depends(get_refresh_claims)],
    refresh: Annotated[RefreshUserSession, Depends(get_refresh_user_session)],
) -> AccessToken:
    """Обновляет токены текущей сессии.

    Продлевает сессию, отзывает предъявленный `refresh`-токен и перечитывает роль из БД. Новый
    `refresh`-токен записывает в HTTP-only cookie; `access`-токен возвращает в теле.

    Args:
        response (Response): Ответ, в который кладётся новый `refresh`-токен (cookie).
        claims (RefreshTokenClaims): Проверенные `claims` `refresh`-токена.
        refresh (RefreshUserSession): Сценарий обновления сессии.

    Returns:
        AccessToken: Новый `access`-токен с параметрами.
    """
    pair = await refresh(claims)

    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=pair.refresh_token,
        max_age=config.security.REFRESH_TOKEN_TTL,
        httponly=True,
        secure=not config.app.DEBUG,
        samesite="lax",
    )

    return AccessToken(access_token=pair.access_token, expires_in=pair.expires_in)


@router.post("/logout", response_class=Response, **LOGOUT_DOCS)
async def logout_user(
    claims: Annotated[RefreshTokenClaims, Depends(get_refresh_token)],
    revoke: Annotated[RevokeSession, Depends(get_revoke_session)],
    response: Response,
) -> None:
    """Отзывает сессию и удаляет cookie `refresh`-токена.

    Args:
        claims (RefreshTokenClaims): Проверенные `claims` `refresh`-токена сессии.
        revoke (RevokeSession): Use case отзыва сессии.
        response (Response): Ответ, из которого удаляется `refresh`-токен (cookie).
    """
    await revoke(claims)
    response.delete_cookie(REFRESH_TOKEN_COOKIE)
