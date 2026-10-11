"""Тесты схем документа JWKS."""

from pydantic import ValidationError
import pytest

from src.api.well_known.schemas import JSONWebKeySet

KEY_ID = "nzbLsXh8uDCcd-6MNwXF4W_7noWXFZAfHkxZsRGC9Xs"
PUBLIC_PART = "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo"


def _eddsa_key() -> dict[str, str]:
    """Собирает публичный ключ EdDSA для проверок.

    Returns:
        dict[str, str]: Публичный ключ в формате RFC 8037.
    """
    return {
        "kty": "OKP",
        "use": "sig",
        "kid": KEY_ID,
        "alg": "EdDSA",
        "crv": "Ed25519",
        "x": PUBLIC_PART,
    }


def test_jsonwebkeyset_passes_eddsa_key_through() -> None:
    """Публичный ключ EdDSA.

    Given: документ JWKS с публичным ключом Ed25519,
    When: документ приводится к схеме ответа,
    Then: набор отдаёт этот ключ без потери полей.
    """
    # Дано
    document = {"keys": [_eddsa_key()]}

    # Когда
    key_set = JSONWebKeySet.model_validate(document)

    # Тогда
    assert key_set.model_dump() == document


def test_jsonwebkeyset_defaults_to_empty_key_set() -> None:
    """Пустой документ JWKS.

    Given: ключи ещё не публиковались,
    When: ответ собирается без набора ключей,
    Then: набор пуст — потребителю отдаётся корректный пустой ответ.
    """
    # Когда
    key_set = JSONWebKeySet.model_validate({})

    # Тогда
    assert key_set.keys == []


def test_jsonwebkeyset_rejects_unsupported_curve() -> None:
    """Кривая, которую сервис не выпускает.

    Given: документ JWKS с кривой P-256 у ключа типа OKP,
    When: документ приводится к схеме ответа,
    Then: схема отвергает ключ: набор публикует только Ed25519.
    """
    # Дано
    document = {"keys": [_eddsa_key() | {"crv": "P-256"}]}

    # Когда / Тогда
    with pytest.raises(ValidationError, match="crv"):
        JSONWebKeySet.model_validate(document)


def test_jsonwebkeyset_rejects_key_without_public_part() -> None:
    """Ключ без публичной части.

    Given: ключ без параметра `x` с публичной частью,
    When: документ приводится к схеме ответа,
    Then: схема отвергает ключ: публиковать нечего.
    """
    # Дано
    key = _eddsa_key()
    del key["x"]

    # Когда / Тогда
    with pytest.raises(ValidationError, match="x"):
        JSONWebKeySet.model_validate({"keys": [key]})
