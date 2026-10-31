from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, cast

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import jwt
from jwt import PyJWK

from src.application.security import SIGNING_ALGORITHM, key_to_jwk
from src.domain.enums import TokenType
from src.domain.errors import (
    JWTDecryptionError,
    JWTEncryptionError,
    TokenRevokedError,
    UserAuthorizationError,
)
from src.domain.ports import PrivateJwkRepository, PublicJwkRepository, RevokedTokensRepository
from src.domain.tokens import AccessTokenClaims, TokenConfig

from ._base import AbstractUseCase


class SignToken(AbstractUseCase):
    """Use case подписи JWT-токена."""

    def __init__(self, config: TokenConfig, key_repository: PrivateJwkRepository) -> None:
        """Инициализация класса.

        Args:
            config (TokenConfig): Конфигурация выпускаемого токена.
            key_repository (PrivateJwkRepository): Порт приватного ключа подписи.
        """
        self._config = config
        self._private_key = key_repository

    async def __call__(
        self, subject: int | str, session: str, *, not_required: Mapping[str, Any] | None = None
    ) -> tuple[str, int]:
        """Подписывает токен по конфигурации.

        Args:
            subject (int | str): Идентификатор пользователя (`sub`).
            session (str): Идентификатор сессии.
            not_required (Mapping[str, Any] | None, optional): Дополнительные claims,
                объединяемые с базовыми через `|`. Defaults to None.

        Raises:
            JWTEncryptionError: Файл ключа отсутствует, не читается как PEM или
                содержит ключ другого алгоритма.

        Returns:
            tuple[str, int]: Подписанный JWT и срок жизни в секундах (`expires_in`).
        """
        private_key = await self._acquire_private_key()
        key_id = key_to_jwk(private_key)["kid"]

        headers = self._config.build_headers(key_id)
        claims = self._config.build_claims(subject, session)

        if not_required:
            claims = claims | not_required

        token = jwt.encode(claims, private_key, algorithm=SIGNING_ALGORITHM, headers=dict(headers))

        return token, self._config.ttl

    async def _acquire_private_key(self) -> Ed25519PrivateKey:
        """Читает приватный ключ подписи из keyfile.

        Raises:
            JWTEncryptionError: Файл отсутствует, не читается как PEM или содержит
                ключ чужого алгоритма.

        Returns:
            Ed25519PrivateKey: Приватный ключ подписи.
        """
        if (pem := await self._private_key.acquire()) is None:
            msg = "Signing key file is missing."
            raise JWTEncryptionError(msg) from None

        try:
            private_key = serialization.load_pem_private_key(pem, password=None)

        except (TypeError, ValueError) as error:
            msg = "Signing key file is not a valid PEM private key."
            raise JWTEncryptionError(msg) from error

        if not isinstance(private_key, Ed25519PrivateKey):
            msg = "Signing key file does not contain an Ed25519 key."
            raise JWTEncryptionError(msg) from None

        return private_key


class VerifyToken(AbstractUseCase):
    """Use case проверки подписанного JWT-токена."""

    def __init__(self, config: TokenConfig, key_repository: PublicJwkRepository) -> None:
        """Инициализация класса.

        Args:
            config (TokenConfig): Конфигурация проверяемого токена.
            key_repository (PublicJwkRepository): Порт опубликованных публичных JWK.
        """
        self._config = config
        self._public_key = key_repository

    async def __call__(self, token: str, *, audience: str | None = None) -> AccessTokenClaims:
        """Проверяет токен и возвращает его claims.

        Args:
            token (str): Подписанный JWT.
            audience (str | None, optional): Ожидаемая аудитория вместо заданной
                в конфигурации. Defaults to None.

        Raises:
            JWTDecryptionError: Заголовок повреждён, ключ не опубликован, подпись не
                сходится или claims не прошли проверку.

        Returns:
            AccessTokenClaims: Проверенные claims токена.
        """
        key_id = self._get_key_id(token)

        if (jwk := await self._public_key.acquire(key_id)) is None:
            msg = "Token signing key is not published."
            raise JWTDecryptionError(msg) from None

        try:
            claims = jwt.decode(
                token,
                key=PyJWK.from_dict(jwk).key,
                algorithms=[SIGNING_ALGORITHM],
                audience=audience or self._config.audience,
                issuer=self._config.issuer,
                options={"require": list(self._config.required_claims())},
            )

        except jwt.PyJWTError as error:
            msg = "Token is invalid."
            raise JWTDecryptionError(msg) from error

        return cast("AccessTokenClaims", claims)

    @staticmethod
    def _get_key_id(token: str) -> str:
        """Возвращает `kid` из заголовка токена без проверки подписи.

        Args:
            token (str): Подписанный JWT.

        Raises:
            JWTDecryptionError: Заголовок не читается или в нём нет `kid`.

        Returns:
            str: Идентификатор ключа подписи.
        """
        try:
            header = jwt.get_unverified_header(token)

        except jwt.PyJWTError as error:
            msg = "Token header is invalid."
            raise JWTDecryptionError(msg) from error

        key_id = header.get("kid")

        if not isinstance(key_id, str) or not key_id:
            msg = "Token header does not contain a key ID."
            raise JWTDecryptionError(msg) from None

        return key_id


class EnsureTokenActive(AbstractUseCase):
    """Use case проверки, что токен не отозван."""

    def __init__(self, tokens: RevokedTokensRepository) -> None:
        """Инициализация класса.

        Args:
            tokens (RevokedTokensRepository): Порт доступа к отозванным токенам.
        """
        self._tokens = tokens

    async def __call__(
        self, claims: AccessTokenClaims, token_type: TokenType = TokenType.ACCESS
    ) -> None:
        """Проверяет, что токен не отозван.

        Args:
            claims (AccessTokenClaims): Проверенные claims токена.
            token_type (TokenType, optional): Тип токена. Defaults to TokenType.ACCESS.

        Raises:
            TokenRevokedError: Токен уже помечен отозванным.
        """
        if await self._tokens.check(token_type, claims["jti"]):
            msg = "Token is revoked."
            raise TokenRevokedError(msg) from None


class RevokeToken(AbstractUseCase):
    """Use case отзыва выданного токена."""

    def __init__(self, tokens: RevokedTokensRepository) -> None:
        """Инициализация класса.

        Args:
            tokens (RevokedTokensRepository): Порт доступа к отозванным токенам.
        """
        self._tokens = tokens

    async def __call__(
        self, claims: AccessTokenClaims, token_type: TokenType = TokenType.ACCESS
    ) -> None:
        """Помечает токен отозванным до истечения его срока действия.

        Запись в Redis получает TTL, равный остатку срока жизни токена. Если токен уже
        истёк, запись не создаётся: проверять его отзыв больше не нужно.

        Args:
            claims (AccessTokenClaims): Проверенные claims токена.
            token_type (TokenType, optional): Тип токена. Defaults to TokenType.ACCESS.
        """
        if (ttl := claims["exp"] - int(datetime.now(UTC).timestamp())) <= 0:
            return

        await self._tokens.store(token_type, claims["jti"], ttl)


class Authorize(AbstractUseCase):
    """Use case авторизации запроса по Bearer-токену."""

    def __init__(self, verify: VerifyToken, ensure_active: EnsureTokenActive) -> None:
        """Инициализация класса.

        Args:
            verify (VerifyToken): Use case проверки JWT-токена.
            ensure_active (EnsureTokenActive): Use case проверки отзыва токена.
        """
        self._verify = verify
        self._ensure_active = ensure_active

    async def __call__(self, token: str | None) -> AccessTokenClaims:
        """Проверяет Bearer-токен и возвращает его claims.

        Args:
            token (str | None): Токен из заголовка `Authorization` или None, если
                заголовок отсутствует.

        Raises:
            UserAuthorizationError: Токен не передан.
            JWTDecryptionError: Токен недействителен, просрочен или уже отозван.

        Returns:
            AccessTokenClaims: Проверенные claims токена.
        """
        if token is None:
            msg = "Bearer token is missing."
            raise UserAuthorizationError(msg)

        claims = await self._verify(token)
        await self._ensure_active(claims)

        return claims
