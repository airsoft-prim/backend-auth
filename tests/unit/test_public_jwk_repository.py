"""Тесты репозитория публичных JWK в Redis."""

import json

from jwt.types import JWKDict
import pytest

from src.general.exceptions import RepositoryError
from src.providers.cache.repositories import PublicJWKRepository
from tests.doubles import InMemoryRedis

KEY_ID = "nzbLsXh8uDCcd-6MNwXF4W_7noWXFZAfHkxZsRGC9Xs"
OTHER_KEY_ID = "-EVIID9vcCmyTrTngIAcRqaLT0YXT1eMn0BJEYEHr3c"
KEY_TTL_SECONDS = 3600


def _jwk(key_id: str) -> JWKDict:
    """Собирает публичный JWK для проверок.

    Args:
        key_id (str): Идентификатор ключа.

    Returns:
        JWKDict: Публичный JWK в формате RFC 7517.
    """
    return {
        "kty": "OKP",
        "crv": "Ed25519",
        "x": "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo",
        "alg": "EdDSA",
        "use": "sig",
        "kid": key_id,
    }


async def test_store_writes_jwk_json_under_key_with_kid(
    jwk_repository: PublicJWKRepository,
    redis_double: InMemoryRedis,
) -> None:
    """Сохранение публичного ключа.

    Given: репозиторий и публичный JWK,
    When: ключ сохраняется,
    Then: в Redis он лежит по ключу со своим `kid` в виде JSON.
    """
    # Дано
    jwk = _jwk(KEY_ID)

    # Когда
    await jwk_repository.store(KEY_ID, jwk)

    # Тогда
    assert set(redis_double.values) == {f"jwk:{KEY_ID}"}
    assert json.loads(redis_double.values[f"jwk:{KEY_ID}"]) == jwk


async def test_acquire_returns_stored_jwk(jwk_repository: PublicJWKRepository) -> None:
    """Чтение публичного ключа.

    Given: публичный JWK сохранён,
    When: ключ запрашивается по своему `kid`,
    Then: возвращается тот же JWK.
    """
    # Дано
    jwk = _jwk(KEY_ID)
    await jwk_repository.store(KEY_ID, jwk)

    # Когда
    stored = await jwk_repository.acquire(KEY_ID)

    # Тогда
    assert stored == jwk


async def test_acquire_returns_none_for_unknown_key(jwk_repository: PublicJWKRepository) -> None:
    """Чтение неопубликованного ключа.

    Given: ключ с таким `kid` не публиковался,
    When: ключ запрашивается,
    Then: репозиторий сообщает об отсутствии значения, а не падает.
    """
    # Когда
    stored = await jwk_repository.acquire(KEY_ID)

    # Тогда
    assert stored is None


async def test_acquire_all_returns_every_published_jwk(jwk_repository: PublicJWKRepository) -> None:
    """Чтение всего набора публичных ключей.

    Given: опубликованы два публичных JWK,
    When: репозиторий отдаёт весь набор,
    Then: в наборе оба ключа.
    """
    # Дано
    await jwk_repository.store(KEY_ID, _jwk(KEY_ID))
    await jwk_repository.store(OTHER_KEY_ID, _jwk(OTHER_KEY_ID))

    # Когда
    published = await jwk_repository.acquire_all()

    # Тогда
    assert {key["kid"] for key in published} == {KEY_ID, OTHER_KEY_ID}


async def test_expire_rotated_sets_ttl_for_previous_keys_only(
    jwk_repository: PublicJWKRepository,
    redis_double: InMemoryRedis,
) -> None:
    """Время жизни ключей прошлых ротаций.

    Given: опубликованы два публичных JWK и один из них — только что созданный,
    When: репозиторий ограничивает время жизни ключей прошлых ротаций,
    Then: срок получает только прошлый ключ: новый ключ остаётся без ограничения.
    """
    # Дано
    await jwk_repository.store(KEY_ID, _jwk(KEY_ID))
    await jwk_repository.store(OTHER_KEY_ID, _jwk(OTHER_KEY_ID))

    # Когда
    await jwk_repository.expire_rotated(OTHER_KEY_ID, KEY_TTL_SECONDS)

    # Тогда
    assert redis_double.ttl == {f"jwk:{KEY_ID}": KEY_TTL_SECONDS}


def test_compile_template_fills_missing_kid_with_glob(
    jwk_repository: PublicJWKRepository,
) -> None:
    """Сборка ключа Redis из шаблона.

    Given: шаблон ключа публичного JWK,
    When: шаблон собирается с `kid` и без него,
    Then: известный `kid` подставляется, а пропущенный превращается в glob-маску.
    """
    # Когда / Тогда
    assert jwk_repository.compile_template({"kid": KEY_ID}) == f"jwk:{KEY_ID}"
    assert jwk_repository.compile_template({}) == "jwk:*"


async def test_store_translates_transport_failure_into_repository_error(
    unavailable_repository: PublicJWKRepository,
) -> None:
    """Отказ транспорта Redis при записи.

    Given: Redis недоступен,
    When: репозиторий сохраняет публичный ключ,
    Then: ошибка транспорта превращается в ошибку репозитория с понятным текстом.
    """
    # Когда / Тогда
    with pytest.raises(RepositoryError, match="saving error"):
        await unavailable_repository.store(KEY_ID, _jwk(KEY_ID))
