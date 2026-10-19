"""Тесты генерации приватного JWK и публикации его публичной части."""

from base64 import urlsafe_b64encode
from hashlib import sha256
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
import pytest

from src.general.exceptions import ServiceError
from src.providers.filesystem.repositories import PrivateJWKRepository
from src.services.jwk import JWKGenerationService
from tests.doubles import InMemoryRedis

KEY_TTL_SECONDS = 3600
RSA_KEY_SIZE = 2048
RSA_PUBLIC_EXPONENT = 65537


def _rsa_pem() -> bytes:
    """Собирает PEM приватного ключа RSA — чужого алгоритма для сервиса.

    Returns:
        bytes: Закодированный приватный ключ RSA.
    """
    private_key = rsa.generate_private_key(
        public_exponent=RSA_PUBLIC_EXPONENT,
        key_size=RSA_KEY_SIZE,
    )

    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _encode_public_key(public_key: Ed25519PublicKey) -> str:
    """Кодирует публичный ключ Ed25519 в base64url без паддинга, как RFC 8037.

    Args:
        public_key (Ed25519PublicKey): Публичный ключ.

    Returns:
        str: Публичная часть ключа для параметра `x` JWK.
    """
    raw = public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    return urlsafe_b64encode(raw).rstrip(b"=").decode()


async def test_generate_jwk_publishes_new_key_when_store_is_empty(
    jwk_service: JWKGenerationService,
    key_store_dir: Path,
    redis_double: InMemoryRedis,
) -> None:
    """Генерация ключа подписи с нуля.

    Given: каталог ключей пуст и в кеше нет опубликованных JWK,
    When: сервис генерирует ключ подписи,
    Then: приватный ключ записан в файл, а его публичная часть опубликована в кеше.
    """
    # Дано
    key_file = key_store_dir / PrivateJWKRepository.FILE_NAME
    assert not key_file.exists()

    # Когда
    published = await jwk_service.generate_jwk(KEY_TTL_SECONDS)

    # Тогда
    assert key_file.exists()
    assert set(redis_double.values) == {f"jwk:{published.key_id}"}
    assert redis_double.ttl == {}

    jwk = json.loads(redis_double.values[f"jwk:{published.key_id}"])
    private_key = serialization.load_pem_private_key(key_file.read_bytes(), password=None)

    assert isinstance(private_key, Ed25519PrivateKey)
    assert jwk["kty"] == "OKP"
    assert jwk["crv"] == "Ed25519"
    assert jwk["alg"] == "EdDSA"
    assert jwk["use"] == "sig"
    assert jwk["kid"] == published.key_id
    assert jwk["x"] == _encode_public_key(private_key.public_key())
    assert "d" not in jwk


async def test_generate_jwk_keeps_existing_key_when_it_is_published(
    jwk_service: JWKGenerationService,
    key_store_dir: Path,
    redis_double: InMemoryRedis,
) -> None:
    """Повторная генерация при уже опубликованном ключе.

    Given: ключ подписи уже сгенерирован и опубликован,
    When: сервис просят сгенерировать ключ повторно,
    Then: ключ не перегенерируется: файл и кеш остаются прежними.
    """
    # Дано
    first = await jwk_service.generate_jwk(KEY_TTL_SECONDS)
    key_file = key_store_dir / PrivateJWKRepository.FILE_NAME
    stored_values = dict(redis_double.values)
    stored_pem = key_file.read_bytes()

    # Когда
    second = await jwk_service.generate_jwk(KEY_TTL_SECONDS)

    # Тогда
    assert second.key_id == first.key_id
    assert redis_double.values == stored_values
    assert key_file.read_bytes() == stored_pem


async def test_generate_jwk_republishes_existing_key_after_cache_loss(
    jwk_service: JWKGenerationService,
    key_store_dir: Path,
    redis_double: InMemoryRedis,
) -> None:
    """Повторная публикация ключа, пропавшего из кеша.

    Given: приватный ключ есть в файле, но публичный JWK в кеше отсутствует,
    When: сервис генерирует ключ,
    Then: ключ не перегенерируется, а его публичная часть публикуется заново.
    """
    # Дано
    first = await jwk_service.generate_jwk(KEY_TTL_SECONDS)
    key_file = key_store_dir / PrivateJWKRepository.FILE_NAME
    stored_pem = key_file.read_bytes()
    redis_double.values.clear()

    # Когда
    second = await jwk_service.generate_jwk(KEY_TTL_SECONDS)

    # Тогда
    assert second.key_id == first.key_id
    assert set(redis_double.values) == {f"jwk:{first.key_id}"}
    assert key_file.read_bytes() == stored_pem
    assert redis_double.ttl == {}


async def test_generate_jwk_overwrites_key_and_expires_previous_one(
    jwk_service: JWKGenerationService,
    key_store_dir: Path,
    redis_double: InMemoryRedis,
) -> None:
    """Ротация ключа подписи.

    Given: ключ подписи уже сгенерирован и опубликован,
    When: сервис генерирует ключ с перезаписью,
    Then: появляется новый ключ, а прошлый публичный JWK получает время жизни.
    """
    # Дано
    first = await jwk_service.generate_jwk(KEY_TTL_SECONDS)
    key_file = key_store_dir / PrivateJWKRepository.FILE_NAME
    stored_pem = key_file.read_bytes()

    # Когда
    second = await jwk_service.generate_jwk(KEY_TTL_SECONDS, overwrite=True)

    # Тогда
    assert second.key_id != first.key_id
    assert key_file.read_bytes() != stored_pem
    assert set(redis_double.values) == {f"jwk:{first.key_id}", f"jwk:{second.key_id}"}
    assert redis_double.ttl == {f"jwk:{first.key_id}": KEY_TTL_SECONDS}


async def test_generate_jwk_rejects_key_file_with_foreign_algorithm(
    jwk_service: JWKGenerationService,
    key_store_dir: Path,
) -> None:
    """Ключ чужого алгоритма в файле.

    Given: в файле ключа подписи лежит ключ RSA, а не Ed25519,
    When: сервис генерирует ключ,
    Then: он сообщает об ошибке, а не публикует несовместимый ключ.
    """
    # Дано
    key_file = key_store_dir / PrivateJWKRepository.FILE_NAME
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_bytes(_rsa_pem())

    # Когда / Тогда
    with pytest.raises(ServiceError, match="does not contain an Ed25519 key"):
        await jwk_service.generate_jwk(KEY_TTL_SECONDS)


async def test_published_key_id_is_rfc7638_thumbprint(
    jwk_service: JWKGenerationService,
    redis_double: InMemoryRedis,
) -> None:
    """Идентификатор ключа.

    Given: сервис сгенерировал ключ подписи,
    When: публичный JWK попадает в кеш,
    Then: его `kid` — отпечаток ключа по RFC 7638, а не произвольное значение.
    """
    # Дано / Когда
    published = await jwk_service.generate_jwk(KEY_TTL_SECONDS)

    # Тогда
    jwk = json.loads(redis_double.values[f"jwk:{published.key_id}"])
    thumbprint = json.dumps(
        {"crv": jwk["crv"], "kty": jwk["kty"], "x": jwk["x"]},
        separators=(",", ":"),
        sort_keys=True,
    )
    expected = urlsafe_b64encode(sha256(thumbprint.encode()).digest()).rstrip(b"=").decode()

    assert published.key_id == expected
    assert "=" not in published.key_id
