from base64 import urlsafe_b64encode
from collections.abc import Sequence
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Final

import aiofiles
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from jwt import PyJWK
from jwt.algorithms import get_default_algorithms
from jwt.types import JWKDict
from loguru import logger

from src.general.exceptions import ServiceError
from src.providers.cache.repositories import PublicJWKRepository

_KEY_FILE_PERMISSIONS: Final[int] = 0o600


class JWKPublishingService:
    """Сервис публикации публичных JWK подписи токенов.

    Отдаёт набор публичных ключей из кеша, чтобы потребители токенов проверяли подпись
    офлайн, по ключам из JWKS, и не обращались за этим к сервису на каждый запрос.
    """

    def __init__(self, jwk_repository: PublicJWKRepository) -> None:
        """Инициализация класса.

        Args:
            jwk_repository (PublicJWKRepository): Репозиторий публичных JWK.
        """
        self._cache = jwk_repository

    async def collect(self) -> Sequence[JWKDict]:
        """Собирает опубликованные публичные JWK.

        Returns:
            Sequence[JWKDict]: Публичные JWK, доступные для проверки подписи.

        Raises:
            RepositoryError: Если обращение к Redis завершилось ошибкой.
        """
        return await self._cache.acquire_all()


class JWKGenerationService:
    """Сервисный класс генерации JWK для подписи JWT.

    Сервис работает исключительно с ключами алгоритма EdDSA на кривой Ed25519.
    """

    KEY_USE: str = "sig"
    KEY_FILE: str = "private-jwk.pem"
    ALGORITHM: str = "EdDSA"

    def __init__(self, key_store_dir: Path, jwk_repository: PublicJWKRepository) -> None:
        """Инициализация класса.

        Args:
            key_store_dir (Path): Директория для хранения сгенерированных ключей.
            jwk_repository (PublicJWKRepository): Репозиторий для хранения публичных JWK.
        """
        self._key_path = key_store_dir / self.KEY_FILE
        self._cache = jwk_repository

    async def generate_jwk(self, rotated_ttl: int, *, overwrite: bool = False) -> PyJWK:
        """Генерирует приватный JWK.

        Если ключ уже существует, а флаг перезаписи не был передан, то сервис не будет
        генерировать новый приватный JWK ключ, а лишь проверит существование соответствующего
        ему публичного JWK ключа в Redis.

        Args:
            rotated_ttl (int): Время жизни публичных JWK, чья приватная пара была ротированна.
            overwrite (bool, optional): Флаг перезаписи ключа, если он уже существует.
                Defaults to False.
        """
        if self._key_path.exists(follow_symlinks=True) and not overwrite:
            logger.info("Key file already exists. Generation will be skipped.")

            private_jwk = await self._read_from_file(self._key_path)
            public_jwk = self._get_public_jwk(private_jwk)

            if await self._cache.acquire(self._get_key_id(public_jwk)) is not None:
                logger.info("Public JWK already published.")
                return public_jwk

        else:
            private_jwk = self._generate_private_jwk()
            public_jwk = self._get_public_jwk(private_jwk)

            await self._write_into_file(self._key_path, private_jwk)
            logger.success("Private JWK generated.")

        kid = self._get_key_id(public_jwk)

        await self._cache.store(kid, self._get_jwk_dict(public_jwk.key))
        await self._cache.expire_rotated(kid, rotated_ttl)
        logger.success("Public JWK published.")

        return public_jwk

    def _generate_private_jwk(self) -> PyJWK:
        """Генерирует приватный JWK, используя кривую Ed25519.

        Returns:
            PyJWK: Приватная часть JWK.
        """
        jwk_dict = self._get_jwk_dict(Ed25519PrivateKey.generate())
        return PyJWK.from_dict(obj=jwk_dict)

    def _get_public_jwk(self, private_jwk: PyJWK) -> PyJWK:
        """Собирает публичный JWK из приватного.

        Args:
            private_jwk (PyJWK): Приватный JWK.

        Returns:
            PyJWK: Публичная часть JWK, пригодная для публикации.
        """
        jwk_dict = self._get_jwk_dict(private_jwk.key.public_key())
        return PyJWK.from_dict(obj=jwk_dict)

    def _get_jwk_dict(self, key: Ed25519PrivateKey | Ed25519PublicKey) -> JWKDict:
        """Сериализует ключ Ed25519 в JWK по RFC 8037.

        Args:
            key (Ed25519PrivateKey | Ed25519PublicKey): Ключ для сериализации. Приватный
                ключ даёт JWK с параметром `d`, публичный — только публичную часть.

        Returns:
            JWKDict: JWK с `alg`, `use` и посчитанным `kid`.
        """
        encryption_algorithm = get_default_algorithms()[self.ALGORITHM]
        jwk: JWKDict = encryption_algorithm.to_jwk(key, as_dict=True)

        jwk["kid"] = self._generate_key_id(jwk)

        jwk["alg"] = self.ALGORITHM
        jwk["use"] = self.KEY_USE

        return jwk

    async def _read_from_file(self, path: Path) -> PyJWK:
        """Читает приватный JWK из PEM-файла.

        Args:
            path (Path): Путь к файлу с приватным ключом.

        Returns:
            PyJWK: Приватный ключ из файла.

        Raises:
            ServiceError: Если файл содержит ключ не на кривой Ed25519.
        """
        async with aiofiles.open(path, "rb") as file:
            pem = await file.read()

        private_key = serialization.load_pem_private_key(pem, password=None)

        if not isinstance(private_key, Ed25519PrivateKey):
            msg = "Private key file does not contain an Ed25519 key."
            raise ServiceError(msg) from None

        return PyJWK.from_dict(self._get_jwk_dict(private_key))

    async def _write_into_file(self, path: Path, jwk: PyJWK) -> None:
        """Записывает приватный JWK в PEM-файл.

        Args:
            path (Path): Путь к файлу с приватным ключом.
            jwk (PyJWK): Приватный JWK для записи.
        """
        private_key: Ed25519PrivateKey = jwk.key
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        path.parent.mkdir(parents=True, exist_ok=True)

        def _descriptor(path: str, flags: int) -> int:
            """Возвращает дескриптор для открытия файла."""
            return os.open(path, flags, _KEY_FILE_PERMISSIONS)

        async with aiofiles.open(path, "wb", opener=_descriptor) as file:
            await file.write(pem)

    @staticmethod
    def _generate_key_id(jwk: JWKDict) -> str:
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

    @staticmethod
    def _get_key_id(jwk: PyJWK) -> str:
        """Возвращает `kid` ключа — им ключ адресуется в кеше.

        Args:
            jwk (PyJWK): JWK с посчитанным `kid`.

        Raises:
            ServiceError: Если у ключа нет `kid`.

        Returns:
            str: `kid` ключа.
        """
        if (key_id := jwk.key_id) is None:
            msg = "JWK does not contain a key ID."
            raise ServiceError(msg) from None

        return key_id
