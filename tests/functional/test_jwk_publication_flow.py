"""Тесты сквозного потока «генерация ключа → публикация → проверка токена»."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from src.services.jwk import JWKGenerationService
from tests.asgi_client import ASGIClient
from tests.doubles import InMemoryRedis
from tests.functional.conftest import TokenSigner

JWKS_PATH = "/.well-known/jwks.json"
ALGORITHM = "EdDSA"
SUBJECT = "42"
TOKEN_LIFETIME = timedelta(hours=24)
ROTATED_TTL_SECONDS = 3600


def _claims() -> dict[str, Any]:
    """Собирает claims access-токена.

    Returns:
        dict[str, Any]: Субъект токена, момент выпуска и срок действия.
    """
    issued_at = datetime.now(UTC)

    return {
        "sub": SUBJECT,
        "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + TOKEN_LIFETIME).timestamp()),
    }


def _select_key(keys: list[dict[str, Any]], key_id: str) -> dict[str, Any]:
    """Выбирает ключ набора по `kid` из заголовка токена.

    Args:
        keys (list[dict[str, Any]]): Публичные ключи из JWKS.
        key_id (str): Идентификатор ключа из заголовка токена.

    Returns:
        dict[str, Any]: Публичный ключ для проверки подписи.
    """
    return next(key for key in keys if key["kid"] == key_id)


def _key_id(public_key: jwt.PyJWK) -> str:
    """Возвращает идентификатор сгенерированного ключа.

    Args:
        public_key (jwt.PyJWK): Публичный ключ из сервиса генерации.

    Returns:
        str: Идентификатор ключа (`kid`).

    Raises:
        AssertionError: У ключа нет идентификатора.
    """
    if public_key.key_id is None:
        msg = "Generated JWK has no key ID."
        raise AssertionError(msg)

    return public_key.key_id


async def test_consumer_verifies_token_with_key_from_jwks(
    jwks_client: ASGIClient,
    jwk_service: JWKGenerationService,
    sign_access_token: TokenSigner,
) -> None:
    """Проверка подписи токена по опубликованному JWKS.

    Given: сервис сгенерировал и опубликовал ключ подписи и выпустил им токен,
    When: потребитель читает JWKS по HTTP и проверяет подпись токена ключом оттуда,
    Then: подпись сходится, а claims токена читаются без обращения к сервису за ключом.
    """
    # Дано
    published = await jwk_service.generate_jwk(ROTATED_TTL_SECONDS)
    token = sign_access_token(_claims(), _key_id(published))

    # Когда
    response = await jwks_client.get(JWKS_PATH)
    public_key = jwt.PyJWK.from_dict(_select_key(response.payload["keys"], _key_id(published)))

    # Тогда
    claims = jwt.decode(token, key=public_key.key, algorithms=[ALGORITHM])
    assert claims["sub"] == SUBJECT


async def test_rotation_keeps_previous_key_published_for_issued_tokens(
    jwks_client: ASGIClient,
    jwk_service: JWKGenerationService,
    redis_double: InMemoryRedis,
    sign_access_token: TokenSigner,
) -> None:
    """Ротация ключа подписи.

    Given: сервис выпустил токен ключом, который затем ротирован,
    When: потребитель читает JWKS после ротации,
    Then: в наборе есть и новый, и прошлый ключ, а прошлый ограничен временем жизни,
    поэтому ранее выданный токен ещё проверяется.
    """
    # Дано
    previous = await jwk_service.generate_jwk(ROTATED_TTL_SECONDS)
    token = sign_access_token(_claims(), _key_id(previous))

    # Когда
    rotated = await jwk_service.generate_jwk(ROTATED_TTL_SECONDS, overwrite=True)
    response = await jwks_client.get(JWKS_PATH)

    # Тогда
    keys = response.payload["keys"]
    assert {key["kid"] for key in keys} == {previous.key_id, rotated.key_id}
    assert redis_double.ttl == {f"jwk:{previous.key_id}": ROTATED_TTL_SECONDS}

    public_key = jwt.PyJWK.from_dict(_select_key(keys, _key_id(previous)))
    claims = jwt.decode(token, key=public_key.key, algorithms=[ALGORITHM])
    assert claims["sub"] == SUBJECT
