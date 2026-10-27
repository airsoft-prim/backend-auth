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
    """Функция смены пароля.

    Args:
        body (ChangePasswordRequestBody): Текущий и новый пароль.
        current_user (Any): Пользователь, которому принадлежит токен.
    """
    raise NotImplementedError


@router.post("/reset", **START_PASSWORD_RESET_DOCS)
async def start_password_reset(body: PasswordResetRequestBody) -> None:
    """Функция запуска сброса пароля.

    Args:
        body (PasswordResetRequestBody): Email учётной записи.
    """
    raise NotImplementedError


@router.patch("/reset", **CONFIRM_PASSWORD_RESET_DOCS)
async def confirm_password_reset(body: PasswordResetConfirmRequestBody) -> None:
    """Функция подтверждения сброса пароля.

    Args:
        body (PasswordResetConfirmRequestBody): Одноразовый токен и новый пароль.
    """
    raise NotImplementedError
