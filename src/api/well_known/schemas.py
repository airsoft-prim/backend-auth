from typing import Annotated, Literal

from pydantic import BaseModel, Field


class PublicJSONWebKey(BaseModel):
    """Общие поля публичного ключа JWK (RFC 7517 §4)."""

    kty: str
    use: Literal["sig", "enc"]
    kid: str


class EdDSAKey(PublicJSONWebKey):
    """Публичный ключ подписи на кривых Ed25519 и Ed448 (RFC 8037 §2)."""

    kty: Literal["OKP"]
    alg: Literal["EdDSA", "Ed25519", "Ed448"]
    crv: Literal["Ed25519", "Ed448"]
    x: str


class RSAKey(PublicJSONWebKey):
    """Публичный ключ подписи RSA (RFC 7518 §6.3)."""

    kty: Literal["RSA"]
    alg: Literal["RS256", "RS384", "RS512", "PS256", "PS384", "PS512"]
    n: str
    e: str


class ECDSAKey(PublicJSONWebKey):
    """Публичный ключ подписи ECDSA (RFC 7518 §6.2, RFC 8812 §3.1)."""

    kty: Literal["EC"]
    alg: Literal["ES256", "ES384", "ES512", "ES256K"]
    crv: Literal["P-256", "P-384", "P-521", "secp256k1"]
    x: str
    y: str


type PublicKey = Annotated[EdDSAKey | ECDSAKey | RSAKey, Field(discriminator="kty")]


class JSONWebKeySet(BaseModel):
    """Модель ответа на запрос JWKS."""

    keys: list[PublicKey] = Field(default_factory=list)
