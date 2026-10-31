from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any, ClassVar, NotRequired, TypedDict
from uuid import uuid4

from src.domain.enums import TokenType


class TokenClaims(TypedDict, total=True):
    """Общие claims любого токена (RFC 7519)."""

    iss: Annotated[str, "Issuer"]
    sub: Annotated[str, "Subject"]
    aud: Annotated[str, "Audience"]
    exp: Annotated[int, "Expiration time"]
    iat: Annotated[int, "Issued at"]
    jti: Annotated[str, "JWT ID"]
    sid: Annotated[str, "Session ID"]


class AccessTokenClaims(TokenClaims, total=True):
    """Claims access-токена."""

    srl: NotRequired[Annotated[str, "Subject Role"]]


class RefreshTokenClaims(TokenClaims, total=True):
    """Claims refresh-токена."""


class TokenHeaders(TypedDict, total=True):
    """Заголовок JWT-токена (общий для всех типов токенов)."""

    typ: Annotated[TokenType, "Token type"]
    kid: Annotated[str, "Key ID"]


@dataclass(frozen=True, slots=True)
class TokenConfig[ClaimsT]:
    """Базовая generic-конфигурация токена, параметризованная типом claims.

    Общие параметры (`issuer`, `audience`, `ttl`) задаются при создании; тип токена и
    тип claims фиксируются подклассом — `AccessTokenConfig` или `RefreshTokenConfig`.
    """

    issuer: str
    audience: str
    ttl: int

    token_type: ClassVar[TokenType]
    claims: ClassVar[type[Any]]

    @classmethod
    def required_claims(cls) -> tuple[str, ...]:
        """Имена обязательных claims — ключи claims-типа без `NotRequired`.

        Returns:
            tuple[str, ...]: Имена claims, без которых токен считается неполным.
        """
        return tuple(cls.claims.__required_keys__)

    def expires_at(self, issued_at: int) -> int:
        """Момент истечения токена, выпущенного в `issued_at` (Unix epoch).

        Args:
            issued_at (int): Момент выпуска токена в секундах Unix epoch.

        Returns:
            int: Момент истечения в секундах Unix epoch.
        """
        return issued_at + self.ttl

    def build_headers(self, kid: str) -> TokenHeaders:
        """Собирает заголовок JWT-токена.

        `typ` берётся из `token_type` конфигурации, `kid` адресует ключ подписи.

        Args:
            kid (str): Идентификатор ключа подписи.

        Returns:
            TokenHeaders: Заголовок JWT-токена.
        """
        return {
            "typ": self.token_type,
            "kid": kid,
        }

    def build_claims(self, subject: int | str, sid: str) -> ClaimsT:
        """Собирает базовые claims токена.

        `iat`/`exp`/`jti` вычисляются сами; `iss`/`aud` берутся из конфигурации.
        Обязательны только `sub` и `sid`.

        Args:
            subject (int | str): Идентификатор пользователя (`sub`).
            sid (str): Идентификатор сессии.

        Returns:
            ClaimsT: Базовые claims токена.
        """
        issued_at = int(datetime.now(UTC).timestamp())

        return self.claims(
            iss=self.issuer,
            sub=str(subject),
            aud=self.audience,
            iat=issued_at,
            exp=self.expires_at(issued_at),
            jti=uuid4().hex,
            sid=sid,
        )


@dataclass(frozen=True, slots=True)
class AccessTokenConfig(TokenConfig[AccessTokenClaims]):
    """Конфигурация access-токена."""

    token_type = TokenType.ACCESS
    claims = AccessTokenClaims


@dataclass(frozen=True, slots=True)
class RefreshTokenConfig(TokenConfig[RefreshTokenClaims]):
    """Конфигурация refresh-токена."""

    token_type = TokenType.REFRESH
    claims = RefreshTokenClaims
