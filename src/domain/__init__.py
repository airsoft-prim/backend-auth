"""Доменная модель аутентификации и сессий.

Определяет сущности, роли, типы и `claims` токенов, ошибки и протоколы доступа к ресурсам.

Задаёт контракты прикладного слоя без зависимости от `FastAPI`, `Redis` и SQLAlchemy.
"""

from .entities import User
from .enums import NiftyStrEnum, TokenType, UserRole
from .errors import (
    ApplicationError,
    DomainError,
    JWTDecryptionError,
    JWTEncryptionError,
    ProviderError,
    RepositoryError,
    SecurityError,
    ServiceError,
    TokenRevokedError,
    UserAlreadyExistsError,
    UserAuthenticationError,
    UserAuthorizationError,
    UserIdentificationError,
)
from .ports import (
    JsonWebKey,
    PasswordHasher,
    PrivateJwkRepository,
    PublicJwkRepository,
    RevokedSessionsRepository,
    RevokedTokensRepository,
    UserRepository,
)
from .tokens import (
    AccessTokenClaims,
    AccessTokenConfig,
    RefreshTokenClaims,
    RefreshTokenConfig,
    TokenClaims,
    TokenConfig,
    TokenHeaders,
)

__all__ = [
    "AccessTokenClaims",
    "AccessTokenConfig",
    "ApplicationError",
    "DomainError",
    "JWTDecryptionError",
    "JWTEncryptionError",
    "JsonWebKey",
    "NiftyStrEnum",
    "PasswordHasher",
    "PrivateJwkRepository",
    "ProviderError",
    "PublicJwkRepository",
    "RefreshTokenClaims",
    "RefreshTokenConfig",
    "RepositoryError",
    "RevokedSessionsRepository",
    "RevokedTokensRepository",
    "SecurityError",
    "ServiceError",
    "TokenClaims",
    "TokenConfig",
    "TokenHeaders",
    "TokenRevokedError",
    "TokenType",
    "User",
    "UserAlreadyExistsError",
    "UserAuthenticationError",
    "UserAuthorizationError",
    "UserIdentificationError",
    "UserRepository",
    "UserRole",
]
