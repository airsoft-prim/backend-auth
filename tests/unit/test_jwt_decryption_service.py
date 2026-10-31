"""Тесты проверки access-токенов."""

from datetime import UTC, datetime
import json
from typing import Any

import jwt
from jwt import PyJWK
import pytest

from src.application.jwk import RotateJwk
from src.application.token import IssueAccessToken, VerifyAccessToken
from src.config import config
from src.domain.errors import JWTDecryptionError
from tests.doubles import InMemoryRedis
from tests.unit.conftest import RawTokenSigner

SUBJECT = 42
SUBJECT_ROLE = "moderator"
TOKEN_ID = "token-under-test"  # noqa: S105
TTL_SECONDS = 3600
HS256_SECRET = "hs256-secret"  # noqa: S105


def _claims() -> dict[str, Any]:
    """Собирает корректный набор claims access-токена без необязательной роли.

    Returns:
        dict[str, Any]: Claims с издателем, аудиторией, субъектом и временем жизни.
    """
    issued_at = int(datetime.now(UTC).timestamp())

    return {
        "iss": config.app.NAME,
        "sub": str(SUBJECT),
        "aud": config.app.PROJECT,
        "iat": issued_at,
        "exp": issued_at + TTL_SECONDS,
        "jti": TOKEN_ID,
    }


def _key_id(public_key: PyJWK) -> str:
    """Возвращает идентификатор опубликованного ключа.

    Args:
        public_key (PyJWK): Публичный ключ сервиса.

    Returns:
        str: Идентификатор ключа (`kid`).

    Raises:
        AssertionError: У ключа нет идентификатора.
    """
    if public_key.key_id is None:
        msg = "Generated JWK has no key ID."
        raise AssertionError(msg)

    return public_key.key_id


async def test_decrypt_returns_claims_of_valid_token(
    issue_access_token: IssueAccessToken,
    verify_access_token: VerifyAccessToken,
    rotate_jwk: RotateJwk,
) -> None:
    """Проверка корректного токена.

    Given: сервис выпустил токен ключом, чья публичная часть опубликована,
    When: потребитель проверяет токен,
    Then: подпись сходится, и он получает издателя, аудиторию, субъекта, роль и `jti`.
    """
    # Дано
    published = await rotate_jwk(TTL_SECONDS)
    token, _ = await issue_access_token(SUBJECT, SUBJECT_ROLE, token_id=TOKEN_ID)

    # Когда
    claims = await verify_access_token(token)

    # Тогда
    assert jwt.get_unverified_header(token)["kid"] == _key_id(published)
    assert claims["iss"] == config.app.NAME
    assert claims["aud"] == config.app.PROJECT
    assert claims["sub"] == str(SUBJECT)
    assert claims["srl"] == SUBJECT_ROLE
    assert claims["jti"] == TOKEN_ID
    assert claims["exp"] > claims["iat"]


async def test_decrypt_accepts_token_without_optional_role(
    verify_access_token: VerifyAccessToken,
    rotate_jwk: RotateJwk,
    raw_token_signer: RawTokenSigner,
) -> None:
    """Проверка токена без необязательного claim роли.

    Given: подпись верна, но кастомного claim `srl` в токене нет,
    When: потребитель проверяет токен,
    Then: сервис принимает токен: роль — необязательный claim.
    """
    # Дано
    published = await rotate_jwk(TTL_SECONDS)
    token = raw_token_signer(_claims(), _key_id(published))

    # Когда
    claims = await verify_access_token(token)

    # Тогда
    assert "srl" not in claims
    assert claims["sub"] == str(SUBJECT)


async def test_decrypt_rejects_token_whose_key_is_not_published(
    issue_access_token: IssueAccessToken,
    verify_access_token: VerifyAccessToken,
    rotate_jwk: RotateJwk,
    redis_double: InMemoryRedis,
) -> None:
    """Проверка токена без опубликованного ключа.

    Given: токен выпущен ключом, который пропал из опубликованного набора JWK,
    When: потребитель проверяет токен,
    Then: сервис отказывает, потому что проверять подпись нечем.
    """
    # Дано
    await rotate_jwk(TTL_SECONDS)
    token, _ = await issue_access_token(SUBJECT)
    redis_double.values.clear()

    # Когда / Тогда
    with pytest.raises(JWTDecryptionError, match="signing key is not published"):
        await verify_access_token(token)


async def test_decrypt_rejects_token_with_broken_signature(
    issue_access_token: IssueAccessToken,
    verify_access_token: VerifyAccessToken,
    rotate_jwk: RotateJwk,
) -> None:
    """Проверка токена с изменённой подписью.

    Given: подпись токена повреждена после выпуска,
    When: потребитель проверяет токен,
    Then: сервис отказывает: подпись не сходится с содержимым токена.
    """
    # Дано
    await rotate_jwk(TTL_SECONDS)
    token, _ = await issue_access_token(SUBJECT)
    header, payload, signature = token.split(".")
    replacement = "A" if signature[0] != "A" else "B"
    broken = ".".join((header, payload, replacement + signature[1:]))

    # Когда / Тогда
    with pytest.raises(JWTDecryptionError, match="Token is invalid"):
        await verify_access_token(broken)


async def test_decrypt_rejects_expired_token(
    issue_access_token: IssueAccessToken,
    verify_access_token: VerifyAccessToken,
    rotate_jwk: RotateJwk,
) -> None:
    """Проверка просроченного токена.

    Given: срок действия токена истёк,
    When: потребитель проверяет токен,
    Then: сервис отказывает, даже если подпись верна.
    """
    # Дано
    await rotate_jwk(TTL_SECONDS)
    token, _ = await issue_access_token(SUBJECT, ttl=-1)

    # Когда / Тогда
    with pytest.raises(JWTDecryptionError, match="Token is invalid"):
        await verify_access_token(token)


async def test_decrypt_rejects_token_without_key_id(
    verify_access_token: VerifyAccessToken,
    rotate_jwk: RotateJwk,
    raw_token_signer: RawTokenSigner,
) -> None:
    """Проверка токена без `kid` в заголовке.

    Given: токен подписан, но заголовок не адресует ключ,
    When: потребитель проверяет токен,
    Then: сервис отказывает: ключ для проверки не выбрать.
    """
    # Дано
    await rotate_jwk(TTL_SECONDS)
    token = raw_token_signer(_claims(), None)

    # Когда / Тогда
    with pytest.raises(JWTDecryptionError, match="does not contain a key ID"):
        await verify_access_token(token)


async def test_decrypt_rejects_malformed_token(verify_access_token: VerifyAccessToken) -> None:
    """Проверка строки, не являющейся JWT.

    Given: вместо токена передана произвольная строка,
    When: потребитель проверяет её,
    Then: сервис отказывает, не пытаясь читать заголовок.
    """
    # Когда / Тогда
    with pytest.raises(JWTDecryptionError, match="Token header is invalid"):
        await verify_access_token("not-a-jwt")


async def test_decrypt_rejects_token_without_required_claim(
    verify_access_token: VerifyAccessToken,
    rotate_jwk: RotateJwk,
    raw_token_signer: RawTokenSigner,
) -> None:
    """Проверка токена без обязательного `jti`.

    Given: подпись верна, но в claims нет идентификатора токена,
    When: потребитель проверяет токен,
    Then: сервис отказывает: без `jti` токен нельзя отозвать при выходе.
    """
    # Дано
    published = await rotate_jwk(TTL_SECONDS)
    claims = _claims()
    claims.pop("jti")
    token = raw_token_signer(claims, _key_id(published))

    # Когда / Тогда
    with pytest.raises(JWTDecryptionError, match="Token is invalid"):
        await verify_access_token(token)


async def test_decrypt_rejects_token_with_foreign_issuer(
    verify_access_token: VerifyAccessToken,
    rotate_jwk: RotateJwk,
    raw_token_signer: RawTokenSigner,
) -> None:
    """Проверка токена с чужим издателем.

    Given: подпись верна, но токен выпущен другим издателем,
    When: потребитель проверяет токен,
    Then: сервис отказывает: токен адресован не этому сервису.
    """
    # Дано
    published = await rotate_jwk(TTL_SECONDS)
    claims = _claims() | {"iss": "foreign-issuer"}
    token = raw_token_signer(claims, _key_id(published))

    # Когда / Тогда
    with pytest.raises(JWTDecryptionError, match="Token is invalid"):
        await verify_access_token(token)


async def test_decrypt_rejects_token_with_foreign_audience(
    verify_access_token: VerifyAccessToken,
    rotate_jwk: RotateJwk,
    raw_token_signer: RawTokenSigner,
) -> None:
    """Проверка токена с чужой аудиторией.

    Given: подпись верна, но токен выпущен для другой аудитории,
    When: потребитель проверяет токен,
    Then: сервис отказывает: токен адресован не ему.
    """
    # Дано
    published = await rotate_jwk(TTL_SECONDS)
    claims = _claims() | {"aud": "foreign-audience"}
    token = raw_token_signer(claims, _key_id(published))

    # Когда / Тогда
    with pytest.raises(JWTDecryptionError, match="Token is invalid"):
        await verify_access_token(token)


async def test_decrypt_rejects_token_with_foreign_algorithm(
    verify_access_token: VerifyAccessToken,
    rotate_jwk: RotateJwk,
) -> None:
    """Проверка токена, подписанного другим алгоритмом.

    Given: токен подписан HS256, а сервис принимает только EdDSA,
    When: потребитель проверяет токен,
    Then: сервис отказывает, не подставляя чужой алгоритм проверки.
    """
    # Дано
    published = await rotate_jwk(TTL_SECONDS)
    token = jwt.encode(
        _claims(),
        HS256_SECRET,
        algorithm="HS256",
        headers={"kid": _key_id(published)},
    )

    # Когда / Тогда
    with pytest.raises(JWTDecryptionError, match="Token is invalid"):
        await verify_access_token(token)


async def test_decrypt_rejects_invalid_published_key(
    verify_access_token: VerifyAccessToken,
    rotate_jwk: RotateJwk,
    raw_token_signer: RawTokenSigner,
    redis_double: InMemoryRedis,
) -> None:
    """Проверка токена при испорченном публичном ключе в кеше.

    Given: по `kid` из заголовка в кеше лежит неполный JWK,
    When: потребитель проверяет токен,
    Then: сервис отказывает, не пропуская токен без проверки подписи.
    """
    # Дано
    published = await rotate_jwk(TTL_SECONDS)
    key_id = _key_id(published)
    redis_double.values[f"jwk:{key_id}"] = json.dumps({"kty": "OKP", "kid": key_id})
    token = raw_token_signer(_claims(), key_id)

    # Когда / Тогда
    with pytest.raises(JWTDecryptionError, match="Token is invalid"):
        await verify_access_token(token)
