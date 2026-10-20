from base64 import urlsafe_b64encode
from hashlib import sha256
import json
from typing import Annotated, Final, NotRequired, TypedDict

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from jwt.algorithms import get_default_algorithms
from jwt.types import JWKDict
from pwdlib import PasswordHash

# Подпись access-токенов и публикуемых ключей: EdDSA на кривой Ed25519.
SIGNING_ALGORITHM: Final[str] = "EdDSA"
SIGNING_KEY_USE: Final[str] = "sig"

# Хешер паролей один на процесс. Argon2id с параметрами по умолчанию.
PASSWORD_HASHER: Final[PasswordHash] = PasswordHash.recommended()


class AccessTokenClaims(TypedDict, total=True):
    """Claims access-токена, которые сервис выпускает и проверяет.

    Каждый атрибут аннотирован согласно RFC 7519.
    """

    iss: Annotated[str, "Issuer"]
    sub: Annotated[str, "Subject"]
    aud: Annotated[str, "Audience"]
    exp: Annotated[int, "Expiration time"]
    iat: Annotated[int, "Issued at"]
    jti: Annotated[str, "JWT ID"]

    # Кастомный необязательный claim: роль есть не у всех потребителей.
    srl: NotRequired[Annotated[str, "Subject Role"]]


def key_to_jwk(key: Ed25519PrivateKey | Ed25519PublicKey) -> JWKDict:
    """Сериализует ключ Ed25519 в JWK по RFC 8037.

    Args:
        key (Ed25519PrivateKey | Ed25519PublicKey): Ключ для сериализации. Приватный
            ключ даёт JWK с параметром `d`, публичный — только публичную часть.

    Returns:
        JWKDict: JWK с `alg`, `use` и посчитанным `kid`.
    """
    encryption_algorithm = get_default_algorithms()[SIGNING_ALGORITHM]
    jwk: JWKDict = encryption_algorithm.to_jwk(key, as_dict=True)

    jwk["kid"] = get_jwk_thumbprint(jwk)
    jwk["alg"] = SIGNING_ALGORITHM
    jwk["use"] = SIGNING_KEY_USE

    return jwk


def get_jwk_thumbprint(jwk: JWKDict) -> str:
    """Считает отпечаток ключа по RFC 7638, который и будет являться ID ключа.

    Отпечаток детерминирован, поэтому `kid` одного и того же ключа не меняется между
    запусками сервиса, и опубликованный ключ всегда находится в кеше по своему `kid`.

    Args:
        jwk (JWKDict): Словарь данных JWK.

    Returns:
        str: Отпечаток ключа.
    """
    payload = {"crv": jwk["crv"], "kty": jwk["kty"], "x": jwk["x"]}
    thumbprint = json.dumps(payload, separators=(",", ":"), sort_keys=True)

    thumbprint_hash = sha256(thumbprint.encode()).digest()

    return urlsafe_b64encode(thumbprint_hash).rstrip(b"=").decode()
