from typing import Required, TypedDict

from pydantic import BaseModel, Field


class PublicKey(TypedDict, total=False):
    """Поля публичного ключа JWK, общие для всех типов ключей (RFC 7517 §4).

    Параметры конкретного типа ключа (`crv` и `x` у OKP, `n` и `e` у RSA)
    описываются в отдельных типах; `key_ops` и поля сертификатов сервис не публикует.
    """

    kty: Required[str]
    use: Required[str]
    alg: Required[str]
    kid: Required[str]


class JSONWebKeySet(BaseModel):
    """Модель ответа на запрос JWKS."""

    keys: list[PublicKey] = Field(default_factory=list)
