"""Фикстуры слоя functional: поток «ключ → публикация → проверка токена»."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import jwt
import pytest

from src.providers.filesystem.repositories import PrivateJWKRepository

__all__ = ["TokenSigner", "sign_access_token"]

ALGORITHM = "EdDSA"

type TokenSigner = Callable[[dict[str, Any], str], str]


@pytest.fixture
def sign_access_token(key_store_dir: Path) -> TokenSigner:
    """Подписывает access-токен приватным ключом сервиса.

    Потребители проверяют такие токены публичным ключом из JWKS. Пока выпуск токенов в
    сервисе не реализован (`JWTService` — заглушка), подпись собирается в тесте тем же
    приватным ключом из keyfile, каким её соберёт сервис.

    Args:
        key_store_dir (Path): Каталог приватного ключа подписи.

    Returns:
        TokenSigner: Функция «claims, kid → подписанный токен».
    """

    def _sign(claims: dict[str, Any], key_id: str) -> str:
        key_file = key_store_dir / PrivateJWKRepository.FILE_NAME
        private_key = serialization.load_pem_private_key(key_file.read_bytes(), password=None)

        if not isinstance(private_key, Ed25519PrivateKey):
            msg = "Key store holds a key that is not Ed25519."
            raise TypeError(msg)

        return jwt.encode(claims, private_key, algorithm=ALGORITHM, headers={"kid": key_id})

    return _sign
