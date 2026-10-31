from typing import Annotated

from fastapi import APIRouter, Body, Depends, Response

from src.application.auth import GetUser, LoginUser, RegisterUser
from src.application.session import CreateSession
from src.application.token import (
    REFRESH_TOKEN_COOKIE,
    IssueTokenPair,
    RevokeSession,
    RotateRefreshToken,
)
from src.config import config
from src.domain.entities import User
from src.domain.tokens import RefreshTokenClaims

from .deps import (
    get_create_session,
    get_current_user,
    get_issue_token_pair,
    get_login_user,
    get_refresh_token,
    get_register_user,
    get_revoke_session,
    get_rotate_refresh_token,
    get_user,
)
from .docs import LOGIN_DOCS, LOGOUT_DOCS, ME_DOCS, REFRESH_DOCS, REGISTER_DOCS
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
    response: Response,
    body: Annotated[LoginRequestBody, Body(...)],
    login: Annotated[LoginUser, Depends(get_login_user)],
    create_session: Annotated[CreateSession, Depends(get_create_session)],
    issue_tokens: Annotated[IssueTokenPair, Depends(get_issue_token_pair)],
) -> AccessToken:
    """Функция входа в систему.

    Args:
        response (Response): Ответ, в который кладётся refresh-токен (cookie).
        body (LoginRequestBody): Учётные данные пользователя.
        login (LoginUser): Use case входа.
        create_session (CreateSession): Use case создания сессии.
        issue_tokens (IssueTokenPair): Use case выпуска пары токенов.

    Returns:
        AccessToken: Выпущенный access-токен с параметрами.
    """
    subject, role = await login(body.username, body.password.get_secret_value())
    session = await create_session(subject)

    pair = await issue_tokens(subject, session.id, role)

    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=pair.refresh_token,
        max_age=config.security.REFRESH_TOKEN_TTL,
        httponly=True,
        secure=not config.app.DEBUG,
        samesite="lax",
    )

    return AccessToken(access_token=pair.access_token, expires_in=pair.expires_in)


@router.get("/me", **ME_DOCS)
async def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> UserData:
    """Функция получения данных учётной записи владельца токена.

    Args:
        current_user (User): Учётная запись владельца проверенного токена.

    Returns:
        UserData: Данные учётной записи без служебных полей.
    """
    return UserData.model_validate(current_user)


@router.post("/refresh", **REFRESH_DOCS)
async def refresh_access_token(
    response: Response,
    claims: Annotated[RefreshTokenClaims, Depends(get_refresh_token)],
    rotate: Annotated[RotateRefreshToken, Depends(get_rotate_refresh_token)],
    fetch_user: Annotated[GetUser, Depends(get_user)],
    issue_tokens: Annotated[IssueTokenPair, Depends(get_issue_token_pair)],
) -> AccessToken:
    """Функция выпуска нового access-токена по действующему refresh-токену.

    Args:
        response (Response): Ответ, в который кладётся новый refresh-токен (cookie).
        claims (RefreshTokenClaims): Проверенные claims refresh-токена.
        rotate (RotateRefreshToken): Use case ротации refresh-токена.
        fetch_user (GetUser): Use case получения учётной записи для роли.
        issue_tokens (IssueTokenPair): Use case выпуска пары токенов.

    Returns:
        AccessToken: Новый access-токен с параметрами.
    """
    await rotate(claims)

    user = await fetch_user(int(claims["sub"]))
    pair = await issue_tokens(claims["sub"], claims["sid"], user.system_role)

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
    """Функция выхода из системы.

    Args:
        claims (RefreshTokenClaims): Проверенные claims refresh-токена сессии.
        revoke (RevokeSession): Use case отзыва сессии.
        response (Response): Ответ, из которого удаляется refresh-токен (cookie).
    """
    await revoke(claims)
    response.delete_cookie(REFRESH_TOKEN_COOKIE)
