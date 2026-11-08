"""Тесты выпуска `access`-токенов."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed448 import Ed448PrivateKey
import jwt
from jwt import PyJWK
import pytest

from src.adapters.filesystem.repositories import FilePrivateJwkRepository
from src.application.jwk import RotateJwk
from src.application.security import SIGNING_ALGORITHM
from src.application.token import SignToken
from src.config import config
from src.domain.errors import JWTEncryptionError
from src.domain.tokens import AccessTokenConfig

SUBJECT = 42
SUBJECT_ROLE = "moderator"
SID = "session-under-test"
TTL_SECONDS = 3600


def _decode(
    token: str,
    public_key: PyJWK,
    *,
    audience: str = config.app.PROJECT,
) -> dict[str, Any]:
    """Проверяет токен и возвращает его `claims`.

    Args:
        token (str): Подписанный JWT.
        public_key (PyJWK): Публичный ключ сервиса.
        audience (str): Ожидаемая аудитория.

    Returns:
        dict[str, Any]: Проверенные `claims` токена.
    """
    return jwt.decode(
        token,
        key=public_key.key,
        algorithms=[SIGNING_ALGORITHM],
        audience=audience,
        issuer=config.app.NAME,
    )


def _foreign_algorithm_pem() -> bytes:
    """Собирает `PEM` ключа Ed448 — алгоритма, который сервис не поддерживает.

    Returns:
        bytes: Закодированный приватный ключ Ed448.
    """
    return Ed448PrivateKey.generate().private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


async def test_signs_token_with_required_header_and_claims(
    sign_token: SignToken,
    rotate_jwk: RotateJwk,
) -> None:
    """Выпуск токена с обязательными заголовком и `claims`.

    Given: у сервиса есть приватный ключ подписи и его публичная часть опубликована, When: сервис
    выпускает токен для пользователя, Then: заголовок содержит `alg`, `typ` и `kid`, а `claims` —
    издателя, аудиторию, субъекта, роль, `jti`, момент выпуска и срок действия из конфигурации.

    Args:
        sign_token (SignToken): Сценарий подписи `access`-токена ключом тестового хранилища.
        rotate_jwk (RotateJwk): Сценарий ротации ключей с тестовыми хранилищами.
    """
    # Дано
    published = await rotate_jwk(TTL_SECONDS)

    # Когда
    token, expires_in = await sign_token(SUBJECT, SID, not_required={"srl": SUBJECT_ROLE})

    # Тогда
    header = jwt.get_unverified_header(token)
    claims = _decode(token, published)

    assert header["alg"] == SIGNING_ALGORITHM
    assert header["typ"] == "access"
    assert header["kid"] == published.key_id
    assert claims["iss"] == config.app.NAME
    assert claims["aud"] == config.app.PROJECT
    assert claims["sub"] == str(SUBJECT)
    assert claims["srl"] == SUBJECT_ROLE
    assert claims["jti"]
    assert claims["exp"] - claims["iat"] == config.security.ACCESS_TOKEN_TTL
    assert expires_in == config.security.ACCESS_TOKEN_TTL


async def test_sign_uses_custom_audience_and_lifetime(
    rotate_jwk: RotateJwk,
    private_jwk_repository: FilePrivateJwkRepository,
) -> None:
    """Выпуск токена с конфигурацией под свою аудиторию и срок жизни.

    Given: у сервиса есть ключ подписи, а use case собран с конфигурацией, задающей свою аудиторию
    и TTL, When: сервис выпускает токен, Then: токен адресован этой аудитории, живёт ровно заданный
    срок, а `expires_in` содержит этот срок в секундах.

    Args:
        rotate_jwk (RotateJwk): Сценарий ротации ключей с тестовыми хранилищами.
        private_jwk_repository (FilePrivateJwkRepository): Репозиторий приватного ключа во
            временном каталоге.
    """
    # Дано
    published = await rotate_jwk(TTL_SECONDS)
    audience = "backend-api"
    issued_before = int(datetime.now(UTC).timestamp())
    custom = SignToken(
        AccessTokenConfig(issuer=config.app.NAME, audience=audience, ttl=TTL_SECONDS),
        private_jwk_repository,
    )

    # Когда
    token, expires_in = await custom(SUBJECT, SID, not_required={"srl": SUBJECT_ROLE})

    # Тогда
    claims = _decode(token, published, audience=audience)

    assert claims["aud"] == audience
    assert claims["exp"] - claims["iat"] == TTL_SECONDS
    assert claims["iat"] >= issued_before
    assert expires_in == TTL_SECONDS


async def test_sign_generates_unique_token_ids(
    sign_token: SignToken,
    rotate_jwk: RotateJwk,
) -> None:
    """Идентификатор токена.

    Given: сервис выпускает два токена подряд, When: каждый токен получает идентификатор, Then:
    идентификаторы непустые и не совпадают.

    Args:
        sign_token (SignToken): Сценарий подписи `access`-токена ключом тестового хранилища.
        rotate_jwk (RotateJwk): Сценарий ротации ключей с тестовыми хранилищами.
    """
    # Дано
    published = await rotate_jwk(TTL_SECONDS)

    # Когда
    first_token, _ = await sign_token(SUBJECT, SID, not_required={"srl": SUBJECT_ROLE})
    second_token, _ = await sign_token(SUBJECT, SID, not_required={"srl": SUBJECT_ROLE})
    first = _decode(first_token, published)
    second = _decode(second_token, published)

    # Тогда
    assert first["jti"]
    assert second["jti"]
    assert first["jti"] != second["jti"]


async def test_sign_rejects_missing_key_file(sign_token: SignToken) -> None:
    """Выпуск токена без keyfile.

    Given: файл приватного ключа ещё не создан, When: сервис пытается выпустить токен, Then: он
    сообщает об отсутствии ключа подписи, а не выпускает неподписанный токен.

    Args:
        sign_token (SignToken): Сценарий подписи `access`-токена ключом тестового хранилища.
    """
    # Когда / Тогда
    with pytest.raises(JWTEncryptionError, match="Signing key file is missing"):
        await sign_token(SUBJECT, SID, not_required={"srl": SUBJECT_ROLE})


async def test_sign_rejects_malformed_key_file(
    sign_token: SignToken,
    key_store_dir: Path,
) -> None:
    """Выпуск токена с повреждённым keyfile.

    Given: в keyfile лежат данные, не являющиеся `PEM`-ключом, When: сервис пытается выпустить
    токен, Then: он сообщает о невалидном ключе подписи.

    Args:
        sign_token (SignToken): Сценарий подписи `access`-токена ключом тестового хранилища.
        key_store_dir (Path): Временный каталог приватного ключа подписи.
    """
    # Дано
    key_file = key_store_dir / FilePrivateJwkRepository.FILE_NAME
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_bytes(b"not a pem private key")

    # Когда / Тогда
    with pytest.raises(JWTEncryptionError, match="not a valid PEM private key"):
        await sign_token(SUBJECT, SID, not_required={"srl": SUBJECT_ROLE})


async def test_sign_rejects_foreign_key_algorithm(
    sign_token: SignToken,
    key_store_dir: Path,
) -> None:
    """Выпуск токена ключом чужого алгоритма.

    Given: в keyfile лежит ключ Ed448, а не Ed25519, When: сервис пытается выпустить токен, Then:
    он отказывается подписывать токен неподдерживаемым ключом.

    Args:
        sign_token (SignToken): Сценарий подписи `access`-токена ключом тестового хранилища.
        key_store_dir (Path): Временный каталог приватного ключа подписи.
    """
    # Дано
    key_file = key_store_dir / FilePrivateJwkRepository.FILE_NAME
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_bytes(_foreign_algorithm_pem())

    # Когда / Тогда
    with pytest.raises(JWTEncryptionError, match="does not contain an Ed25519 key"):
        await sign_token(SUBJECT, SID, not_required={"srl": SUBJECT_ROLE})
