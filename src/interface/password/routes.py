from typing import Any

from fastapi import APIRouter

from .docs import CHANGE_PASSWORD_DOCS, CONFIRM_PASSWORD_RESET_DOCS, START_PASSWORD_RESET_DOCS
from .schemas import (
    ChangePasswordRequestBody,
    PasswordResetConfirmRequestBody,
    PasswordResetRequestBody,
)

router = APIRouter(prefix="/password", tags=["Пароли"])


@router.post("/change", **CHANGE_PASSWORD_DOCS)
async def change_password(body: ChangePasswordRequestBody, current_user: Any) -> None:
    """Обозначает нереализованный маршрут смены пароля.

    Args:
        body (ChangePasswordRequestBody): Текущий и новый пароль.
        current_user (Any): Пользователь, которому принадлежит токен.

    Raises:
        NotImplementedError: Операция не реализована.
    """
    # TODO: после смены пароля отозвать все сессии пользователя по `sid`.
    raise NotImplementedError


@router.post("/reset", **START_PASSWORD_RESET_DOCS)
async def start_password_reset(body: PasswordResetRequestBody) -> None:
    """Обозначает нереализованный маршрут запроса сброса пароля.

    Args:
        body (PasswordResetRequestBody): Email учётной записи.

    Raises:
        NotImplementedError: Операция не реализована.
    """
    raise NotImplementedError


@router.patch("/reset", **CONFIRM_PASSWORD_RESET_DOCS)
async def confirm_password_reset(body: PasswordResetConfirmRequestBody) -> None:
    """Обозначает нереализованный маршрут подтверждения сброса пароля.

    Args:
        body (PasswordResetConfirmRequestBody): Одноразовый токен и новый пароль.

    Raises:
        NotImplementedError: Операция не реализована.
    """
    raise NotImplementedError
