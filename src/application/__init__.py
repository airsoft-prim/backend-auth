"""Прикладные сценарии сервиса аутентификации.

Объединяет регистрацию, вход, работу с сессиями, выпуск и проверку JWT и публикацию JWK.

Использует доменные сущности и порты; вызывается HTTP-интерфейсом и планировщиком.
"""

from ._base import AbstractUseCase
from .auth import GetUser, RegisterUser
from .jwk import CollectJwks, RotateJwk
from .session import (
    CloseSession,
    CreateSession,
    ListSessions,
)
from .token import (
    Authorize,
    EnsureTokenActive,
    IssueTokenPair,
    RevokeSession,
    RotateRefreshToken,
    SignToken,
    VerifyToken,
)

__all__ = [
    "AbstractUseCase",
    "Authorize",
    "CloseSession",
    "CollectJwks",
    "CreateSession",
    "EnsureTokenActive",
    "GetUser",
    "IssueTokenPair",
    "ListSessions",
    "RegisterUser",
    "RevokeSession",
    "RotateJwk",
    "RotateRefreshToken",
    "SignToken",
    "VerifyToken",
]
