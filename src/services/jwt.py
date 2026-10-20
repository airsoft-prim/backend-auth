from datetime import UTC, datetime
from typing import Final, cast
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import jwt
from jwt import PyJWK

from src.core.configs import config
from src.general.exceptions import SecurityError
from src.general.security import SIGNING_ALGORITHM, AccessTokenClaims, key_to_jwk
from src.providers.cache.repositories import PublicJWKRepository
from src.providers.filesystem.repositories import PrivateJWKRepository

TOKEN_TYPE: Final[str] = "JWT"  # noqa: S105

# Без любого из этих claims токен считается неполным, даже если подпись верна.
REQUIRED_CLAIMS: Final[tuple[str, ...]] = ("iss", "sub", "aud", "exp", "iat", "jti")


class JWTEncryptionError(SecurityError):
    """Ошибка выпуска JWT-токена."""


class JWTDecryptionError(SecurityError):
    """Ошибка проверки и чтения JWT-токена."""


class JWTEncryptionService:
    """Сервис выпуска подписанных JWT-токенов."""

    def __init__(self, private_key_repository: PrivateJWKRepository) -> None:
        """Инициализация класса.

        Args:
            private_key_repository (PrivateJWKRepository): Репозиторий приватного ключа подписи.
        """
        self._private_key = private_key_repository

    async def encrypt(
        self,
        subject: int | str,
        subject_role: str | None = None,
        *,
        token_id: str | None = None,
        audience: str | None = None,
        ttl: int | None = None,
    ) -> tuple[str, int]:
        """Подписывает access-токен.

        Args:
            subject (int | str): Идентификатор пользователя (`sub`).
                В JWT он всегда строка, поэтому число приводится к тексту.
            subject_role (str | None, optional): Системная роль пользователя. `None` —
                необязательный claim `srl` в токен не добавляется. Defaults to None.
            token_id (str | None, optional): Идентификатор токена (`jti`).
                Если передано None — генерируется новый. Defaults to None.
            audience (str, optional): Аудитория токена (`aud`).  Defaults to None.
            ttl (int | None): Срок жизни токена в секундах вместо заданного
                при инициализации. Defaults to None.

        Raises:
            JWTEncryptionError: Файл ключа отсутствует, не читается как PEM или
                содержит ключ другого алгоритма.

        Returns:
            tuple[str, int]: Подписанный JWT и срок жизни в секундах (`expires_in`).
        """
        private_key = await self._acquire_private_key()
        key_id = key_to_jwk(private_key)["kid"]

        issued_at = int(datetime.now(UTC).timestamp())

        lifetime = ttl if ttl is not None else config.security.ACCESS_TOKEN_TTL
        expiration = issued_at + lifetime

        claims = {
            "iss": config.app.NAME,
            "sub": str(subject),
            "aud": audience or config.app.PROJECT,
            "iat": issued_at,
            "exp": expiration,
            "jti": token_id if token_id is not None else uuid4().hex,
        }

        if subject_role is not None:
            claims["srl"] = subject_role

        headers = {
            "typ": TOKEN_TYPE,
            "kid": key_id,
        }

        token = jwt.encode(claims, private_key, algorithm=SIGNING_ALGORITHM, headers=headers)

        return token, lifetime

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


class JWTDecryptionService:
    """Сервис проверки подписанных JWT-токенов."""

    def __init__(self, public_key_repository: PublicJWKRepository) -> None:
        """Инициализация класса.

        Args:
            public_key_repository (PublicJWKRepository): Репозиторий опубликованных публичных JWK.
        """
        self._public_key = public_key_repository

    async def decrypt(self, token: str, *, audience: str | None = None) -> AccessTokenClaims:
        """Проверяет access-токен и возвращает его claims.

        Args:
            token (str): Подписанный JWT.

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
                audience=audience or config.app.PROJECT,
                issuer=config.app.NAME,
                options={"require": list(REQUIRED_CLAIMS)},
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

        Returns:
            str: Идентификатор ключа подписи.

        Raises:
            JWTDecryptionError: Заголовок не читается или в нём нет `kid`.
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
