"""Тесты выпуска access-токенов."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed448 import Ed448PrivateKey
import jwt
from jwt import PyJWK
import pytest

from src.core.configs import config
from src.general.security import SIGNING_ALGORITHM
from src.providers.filesystem.repositories import PrivateJWKRepository
from src.services.jwk import JWKGenerationService
from src.services.jwt import JWTEncryptionError, JWTEncryptionService

SUBJECT = 42
SUBJECT_ROLE = "moderator"
TOKEN_ID = "token-under-test"  # noqa: S105
TTL_SECONDS = 3600


def _decode(
    token: str,
    public_key: PyJWK,
    *,
    audience: str = config.app.PROJECT,
) -> dict[str, Any]:
    """Проверяет токен и возвращает его claims.

    Args:
        token (str): Подписанный JWT.
        public_key (PyJWK): Публичный ключ сервиса.
        audience (str, optional): Ожидаемая аудитория. Defaults to `config.app.PROJECT`.

    Returns:
        dict[str, Any]: Проверенные claims токена.
    """
    return jwt.decode(
        token,
        key=public_key.key,
        algorithms=[SIGNING_ALGORITHM],
        audience=audience,
        issuer=config.app.NAME,
    )


def _foreign_algorithm_pem() -> bytes:
    """Собирает PEM ключа Ed448 — алгоритма, который сервис не поддерживает.

    Returns:
        bytes: Закодированный приватный ключ Ed448.
    """
    return Ed448PrivateKey.generate().private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


async def test_encrypt_signs_token_with_required_header_and_claims(
    encryption_service: JWTEncryptionService,
    jwk_service: JWKGenerationService,
) -> None:
    """Выпуск токена с обязательными заголовком и claims.

    Given: у сервиса есть приватный ключ подписи и его публичная часть опубликована,
    When: сервис выпускает токен для пользователя,
    Then: заголовок содержит `alg`, `typ` и `kid`, а claims — издателя, аудиторию,
    субъекта, `jti`, момент выпуска и срок действия из конфигурации.
    """
    # Дано
    published = await jwk_service.generate_jwk(TTL_SECONDS)

    # Когда
    token, expires_in = await encryption_service.encrypt(
        SUBJECT,
        SUBJECT_ROLE,
        token_id=TOKEN_ID,
    )

    # Тогда
    header = jwt.get_unverified_header(token)
    claims = _decode(token, published)

    assert header["alg"] == SIGNING_ALGORITHM
    assert header["typ"] == "JWT"
    assert header["kid"] == published.key_id
    assert claims["iss"] == config.app.NAME
    assert claims["aud"] == config.app.PROJECT
    assert claims["sub"] == str(SUBJECT)
    assert claims["srl"] == SUBJECT_ROLE
    assert claims["jti"] == TOKEN_ID
    assert claims["exp"] - claims["iat"] == config.security.ACCESS_TOKEN_TTL
    assert expires_in == config.security.ACCESS_TOKEN_TTL


async def test_encrypt_uses_custom_audience_and_lifetime(
    encryption_service: JWTEncryptionService,
    jwk_service: JWKGenerationService,
) -> None:
    """Выпуск токена с аудиторией и сроком жизни на один вызов.

    Given: у сервиса есть ключ подписи, а вызывающий код передаёт свою аудиторию и TTL,
    When: сервис выпускает токен,
    Then: токен адресован этой аудитории, живёт ровно переданный срок, а `expires_in`
    содержит этот срок в секундах.
    """
    # Дано
    published = await jwk_service.generate_jwk(TTL_SECONDS)
    audience = "backend-api"
    issued_before = int(datetime.now(UTC).timestamp())

    # Когда
    token, expires_in = await encryption_service.encrypt(
        SUBJECT,
        audience=audience,
        ttl=TTL_SECONDS,
    )

    # Тогда
    claims = _decode(token, published, audience=audience)

    assert claims["aud"] == audience
    assert claims["exp"] - claims["iat"] == TTL_SECONDS
    assert claims["iat"] >= issued_before
    assert expires_in == TTL_SECONDS


async def test_encrypt_omits_optional_role_claim(
    encryption_service: JWTEncryptionService,
    jwk_service: JWKGenerationService,
) -> None:
    """Выпуск токена без необязательного claim роли.

    Given: вызывающий код не передаёт системную роль,
    When: сервис выпускает токен,
    Then: claim `srl` в токен не добавляется, а остальные claims остаются на месте.
    """
    # Дано
    published = await jwk_service.generate_jwk(TTL_SECONDS)

    # Когда
    token, _ = await encryption_service.encrypt(SUBJECT)
    claims = _decode(token, published)

    # Тогда
    assert "srl" not in claims
    assert claims["sub"] == str(SUBJECT)


async def test_encrypt_generates_unique_token_ids(
    encryption_service: JWTEncryptionService,
    jwk_service: JWKGenerationService,
) -> None:
    """Идентификатор токена при выпуске без явного `jti`.

    Given: вызывающий код не передаёт идентификатор токена,
    When: сервис выпускает два токена подряд,
    Then: каждый токен получает собственный непустой `jti` для будущего отзыва.
    """
    # Дано
    published = await jwk_service.generate_jwk(TTL_SECONDS)

    # Когда
    first_token, _ = await encryption_service.encrypt(SUBJECT)
    second_token, _ = await encryption_service.encrypt(SUBJECT)
    first = _decode(first_token, published)
    second = _decode(second_token, published)

    # Тогда
    assert first["jti"]
    assert second["jti"]
    assert first["jti"] != second["jti"]


async def test_encrypt_rejects_missing_key_file(encryption_service: JWTEncryptionService) -> None:
    """Выпуск токена без keyfile.

    Given: файл приватного ключа ещё не создан,
    When: сервис пытается выпустить токен,
    Then: он сообщает об отсутствии ключа подписи, а не выпускает неподписанный токен.
    """
    # Когда / Тогда
    with pytest.raises(JWTEncryptionError, match="Signing key file is missing"):
        await encryption_service.encrypt(SUBJECT)


async def test_encrypt_rejects_malformed_key_file(
    encryption_service: JWTEncryptionService,
    key_store_dir: Path,
) -> None:
    """Выпуск токена с повреждённым keyfile.

    Given: в keyfile лежат данные, не являющиеся PEM-ключом,
    When: сервис пытается выпустить токен,
    Then: он сообщает о невалидном ключе подписи.
    """
    # Дано
    key_file = key_store_dir / PrivateJWKRepository.FILE_NAME
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_bytes(b"not a pem private key")

    # Когда / Тогда
    with pytest.raises(JWTEncryptionError, match="not a valid PEM private key"):
        await encryption_service.encrypt(SUBJECT)


async def test_encrypt_rejects_foreign_key_algorithm(
    encryption_service: JWTEncryptionService,
    key_store_dir: Path,
) -> None:
    """Выпуск токена ключом чужого алгоритма.

    Given: в keyfile лежит ключ Ed448, а не Ed25519,
    When: сервис пытается выпустить токен,
    Then: он отказывается подписывать токен неподдерживаемым ключом.
    """
    # Дано
    key_file = key_store_dir / PrivateJWKRepository.FILE_NAME
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_bytes(_foreign_algorithm_pem())

    # Когда / Тогда
    with pytest.raises(JWTEncryptionError, match="does not contain an Ed25519 key"):
        await encryption_service.encrypt(SUBJECT)
