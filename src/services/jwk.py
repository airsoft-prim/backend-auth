from collections.abc import Sequence

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from jwt import PyJWK
from jwt.types import JWKDict
from loguru import logger

from src.general.exceptions import ServiceError
from src.general.security import key_to_jwk
from src.providers.cache.repositories import PublicJWKRepository
from src.providers.filesystem.repositories import PrivateJWKRepository


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

    def __init__(
        self,
        private_key_repository: PrivateJWKRepository,
        public_key_repossitory: PublicJWKRepository,
    ) -> None:
        """Инициализация класса.

        Args:
            private_key_repository (PrivateJWKRepository): Репозиторий приватного ключа подписи.
            public_key_repossitory (PublicJWKRepository): Репозиторий для хранения публичных JWK.
        """
        self._private_key = private_key_repository
        self._publick_key = public_key_repossitory

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
        if (pem := None if overwrite else await self._private_key.acquire()) is not None:
            logger.info("Key file already exists. Generation will be skipped.")

            private_jwk = self._deserialize_private_jwk(pem)
            public_jwk = self._generate_public_jwk(private_jwk)

            if await self._publick_key.acquire(self._get_jwk_id(public_jwk)) is not None:
                logger.info("Public JWK already published.")
                return public_jwk

        else:
            private_jwk = self._generate_private_jwk()
            public_jwk = self._generate_public_jwk(private_jwk)

            await self._private_key.store(self._serialize_private_jwk(private_jwk))
            logger.success("Private JWK generated.")

        kid = self._get_jwk_id(public_jwk)

        await self._publick_key.store(kid, key_to_jwk(public_jwk.key))
        await self._publick_key.expire_rotated(kid, rotated_ttl)
        logger.success("Public JWK published.")

        return public_jwk

    def _generate_private_jwk(self) -> PyJWK:
        """Генерирует приватный JWK, используя кривую Ed25519.

        Returns:
            PyJWK: Приватная часть JWK.
        """
        jwk_dict = key_to_jwk(Ed25519PrivateKey.generate())
        return PyJWK.from_dict(obj=jwk_dict)

    def _generate_public_jwk(self, private_jwk: PyJWK) -> PyJWK:
        """Генерирует публичный JWK из приватного.

        Args:
            private_jwk (PyJWK): Приватный JWK.

        Returns:
            PyJWK: Публичная часть JWK, пригодная для публикации.
        """
        jwk_dict = key_to_jwk(private_jwk.key.public_key())
        return PyJWK.from_dict(obj=jwk_dict)

    def _deserialize_private_jwk(self, pem: bytes) -> PyJWK:
        """Читает приватный JWK из PEM.

        Args:
            pem (bytes): Приватный ключ в PEM.

        Returns:
            PyJWK: Приватный ключ из файла.

        Raises:
            ServiceError: Если ключ не на кривой Ed25519.
        """
        private_key = serialization.load_pem_private_key(pem, password=None)

        if not isinstance(private_key, Ed25519PrivateKey):
            msg = "Private key file does not contain an Ed25519 key."
            raise ServiceError(msg) from None

        return PyJWK.from_dict(key_to_jwk(private_key))

    def _serialize_private_jwk(self, jwk: PyJWK) -> bytes:
        """Сериализует приватный JWK в PEM (PKCS8).

        Args:
            jwk (PyJWK): Приватный JWK для записи.

        Returns:
            bytes: Приватный ключ в PEM.
        """
        private_key: Ed25519PrivateKey = jwk.key
        return private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

    @staticmethod
    def _get_jwk_id(jwk: PyJWK) -> str:
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
