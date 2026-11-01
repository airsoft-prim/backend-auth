from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import jwt
from jwt import PyJWK

from src.application.security import SIGNING_ALGORITHM, key_to_jwk
from src.application.session import SlideSession
from src.domain.enums import TokenType
from src.domain.errors import (
    JWTDecryptionError,
    JWTEncryptionError,
    TokenRevokedError,
    UserAuthorizationError,
)
from src.domain.ports import (
    PrivateJwkRepository,
    PublicJwkRepository,
    RevokedSessionsRepository,
    RevokedTokensRepository,
    SessionRepository,
)
from src.domain.tokens import RefreshTokenClaims, TokenClaims, TokenConfig

from ._base import AbstractUseCase

REFRESH_TOKEN_COOKIE: Final[str] = "refresh_token"  # noqa: S105


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


@dataclass(frozen=True, slots=True)
class TokenPair:
    """Пара выпущенных токенов сессии (access + refresh)."""

    access_token: str
    refresh_token: str
    expires_in: int


class IssueTokenPair(AbstractUseCase):
    """Use case выпуска пары токенов (access + refresh) для сессии."""

    def __init__(self, access: SignToken, refresh: SignToken) -> None:
        """Инициализация класса.

        Args:
            access (SignToken): Use case подписи access-токена.
            refresh (SignToken): Use case подписи refresh-токена.
        """
        self._access = access
        self._refresh = refresh

    async def __call__(self, subject: int | str, session: str, role: str) -> TokenPair:
        """Выпускает access- и refresh-токены одной сессии.

        Args:
            subject (int | str): Идентификатор пользователя (`sub`).
            session (str): Идентификатор сессии (`sid`).
            role (str): Системная роль пользователя для claim `srl`.

        Returns:
            TokenPair: Подписанная пара токенов и срок жизни access-токена.
        """
        access_token, expires_in = await self._access(subject, session, not_required={"srl": role})
        refresh_token, _ = await self._refresh(subject, session)

        return TokenPair(
            access_token=access_token, refresh_token=refresh_token, expires_in=expires_in
        )


class VerifyToken[ClaimsT](AbstractUseCase):
    """Use case проверки подписанного JWT-токена."""

    def __init__(self, config: TokenConfig[ClaimsT], key_repository: PublicJwkRepository) -> None:
        """Инициализация класса.

        Args:
            config (TokenConfig[ClaimsT]): Конфигурация проверяемого токена.
            key_repository (PublicJwkRepository): Порт опубликованных публичных JWK.
        """
        self._config = config
        self._public_key = key_repository

    async def __call__(self, token: str, *, audience: str | None = None) -> ClaimsT:
        """Проверяет токен и возвращает его claims.

        Args:
            token (str): Подписанный JWT.
            audience (str | None, optional): Ожидаемая аудитория вместо заданной
                в конфигурации. Defaults to None.

        Raises:
            JWTDecryptionError: Заголовок повреждён, ключ не опубликован, подпись не
                сходится или claims не прошли проверку.

        Returns:
            ClaimsT: Проверенные claims токена.
        """
        header = self._get_header(token)

        key_id = header.get("kid")
        if not isinstance(key_id, str) or not key_id:
            msg = "Token header does not contain a key ID."
            raise JWTDecryptionError(msg) from None

        if header.get("typ") != self._config.token_type.value:
            msg = "Token type does not match."
            raise JWTDecryptionError(msg) from None

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

        return self._config.claims(**claims)

    @staticmethod
    def _get_header(token: str) -> dict[str, Any]:
        """Возвращает заголовок токена без проверки подписи.

        Args:
            token (str): Подписанный JWT.

        Raises:
            JWTDecryptionError: Заголовок не читается.

        Returns:
            dict[str, Any]: Заголовок JWT.
        """
        try:
            return jwt.get_unverified_header(token)

        except jwt.PyJWTError as error:
            msg = "Token header is invalid."
            raise JWTDecryptionError(msg) from error


class EnsureTokenActive(AbstractUseCase):
    """Use case проверки, что токен не отозван."""

    def __init__(
        self, tokens: RevokedTokensRepository, sessions: RevokedSessionsRepository
    ) -> None:
        """Инициализация класса.

        Args:
            tokens (RevokedTokensRepository): Порт доступа к отозванным токенам.
            sessions (RevokedSessionsRepository): Порт доступа к отозванным сессиям.
        """
        self._tokens = tokens
        self._sessions = sessions

    async def __call__(self, claims: TokenClaims, token_type: TokenType = TokenType.ACCESS) -> None:
        """Проверяет, что токен не отозван.

        Сначала проверяется, не отозвана ли сессия (`sid`), затем — сам токен (`jti`).

        Args:
            claims (TokenClaims): Проверенные claims токена.
            token_type (TokenType, optional): Тип токена. Defaults to TokenType.ACCESS.

        Raises:
            TokenRevokedError: Токен уже помечен отозванным.
        """
        if await self._sessions.check(claims["sid"]):
            msg = "Token is revoked."
            raise TokenRevokedError(msg) from None

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

    async def __call__(self, claims: TokenClaims, token_type: TokenType = TokenType.ACCESS) -> None:
        """Помечает токен отозванным до истечения его срока действия.

        Запись в Redis получает TTL, равный остатку срока жизни токена. Если токен уже
        истёк, запись не создаётся: проверять его отзыв больше не нужно.

        Args:
            claims (TokenClaims): Проверенные claims токена.
            token_type (TokenType, optional): Тип токена. Defaults to TokenType.ACCESS.
        """
        if (ttl := claims["exp"] - int(datetime.now(UTC).timestamp())) <= 0:
            return

        await self._tokens.store(token_type, claims["jti"], ttl)


class RotateRefreshToken(AbstractUseCase):
    """Use case ротации refresh-токена с обнаружением повторного использования."""

    def __init__(
        self,
        slide_session: SlideSession,
        revoke_token: RevokeToken,
        revoke_session: RevokeSession,
        tokens: RevokedTokensRepository,
        sessions: RevokedSessionsRepository,
    ) -> None:
        """Инициализация класса.

        Args:
            slide_session (SlideSession): Use case продления сессии (sliding expiration).
            revoke_token (RevokeToken): Use case отзыва отдельного токена.
            revoke_session (RevokeSession): Use case отзыва всей сессии при краже.
            tokens (RevokedTokensRepository): Порт доступа к отозванным токенам.
            sessions (RevokedSessionsRepository): Порт доступа к отозванным сессиям.
        """
        self._slide_session = slide_session
        self._revoke_token = revoke_token
        self._revoke_session = revoke_session
        self._tokens = tokens
        self._sessions = sessions

    async def __call__(self, claims: RefreshTokenClaims) -> None:
        """Продлевает сессию и отзывает старый refresh-токен.

        Повторное предъявление уже ротированного refresh-токена — признак кражи:
        в этом случае отзывается вся сессия, а не только предъявленный токен.

        Args:
            claims (RefreshTokenClaims): Проверенные claims refresh-токена.

        Raises:
            TokenRevokedError: Сессия отозвана или refresh-токен уже ротирован.
        """
        if await self._sessions.check(claims["sid"]):
            msg = "Token is revoked."
            raise TokenRevokedError(msg) from None

        if await self._tokens.check(TokenType.REFRESH, claims["jti"]):
            await self._revoke_session(claims)
            msg = "Token is revoked."
            raise TokenRevokedError(msg) from None

        await self._slide_session(claims["sid"])
        await self._revoke_token(claims, TokenType.REFRESH)


class RevokeSession(AbstractUseCase):
    """Use case отзыва сессии по её идентификатору."""

    def __init__(self, revoked: RevokedSessionsRepository, sessions: SessionRepository) -> None:
        """Инициализация класса.

        Args:
            revoked (RevokedSessionsRepository): Порт доступа к отозванным сессиям.
            sessions (SessionRepository): Порт доступа к сессиям пользователей.
        """
        self._revoked = revoked
        self._sessions = sessions

    async def __call__(self, claims: TokenClaims) -> None:
        """Помечает сессию отозванной до истечения срока её действия.

        Срок жизни маркера берётся из записи сессии (`expires_at`), а не из
        предъявленного токена: при повторном использовании refresh-токена его `exp`
        относится к старому токену, тогда как сессия уже продлена новым.

        Все токены сессии (`sid`) становятся недействительными: их проверка в
        `EnsureTokenActive` сначала сверяется с отозванной сессией.

        Args:
            claims (TokenClaims): Проверенные claims refresh-токена сессии.
        """
        now = datetime.now(UTC)
        session = await self._sessions.get(claims["sid"])

        if session is None:
            ttl = claims["exp"] - int(now.timestamp())
        else:
            ttl = int((session.expires_at - now).total_seconds())

        if ttl <= 0:
            return

        await self._revoked.store(claims["sid"], ttl)

        if session is not None and session.revoked_at is None:
            session.revoked_at = now
            await self._sessions.save(session)


class Authorize[ClaimsT: TokenClaims](AbstractUseCase):
    """Use case авторизации запроса по Bearer-токену."""

    def __init__(
        self,
        verify: VerifyToken[ClaimsT],
        ensure_active: EnsureTokenActive,
        token_type: TokenType = TokenType.ACCESS,
    ) -> None:
        """Инициализация класса.

        Args:
            verify (VerifyToken[ClaimsT]): Use case проверки JWT-токена.
            ensure_active (EnsureTokenActive): Use case проверки отзыва токена.
            token_type (TokenType, optional): Тип проверяемого токена.
                Defaults to TokenType.ACCESS.
        """
        self._verify = verify
        self._ensure_active = ensure_active
        self._token_type = token_type

    async def __call__(self, token: str | None) -> ClaimsT:
        """Проверяет Bearer-токен и возвращает его claims.

        Args:
            token (str | None): Токен из заголовка `Authorization` или None, если
                заголовок отсутствует.

        Raises:
            UserAuthorizationError: Токен не передан.
            JWTDecryptionError: Токен недействителен, просрочен или уже отозван.

        Returns:
            ClaimsT: Проверенные claims токена.
        """
        if token is None:
            msg = "Bearer token is missing."
            raise UserAuthorizationError(msg)

        claims = await self._verify(token)
        await self._ensure_active(claims, self._token_type)

        return claims
