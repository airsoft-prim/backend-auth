"""Файловый репозиторий приватного ключа.

Сохраняет и загружает байты `private-jwk.pem` через `FileSystem`.

Реализует `PrivateJwkRepository` для сценариев подписи JWT и ротации ключей.
"""

from .private_jwk import FilePrivateJwkRepository

__all__ = ["FilePrivateJwkRepository"]
