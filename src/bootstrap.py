from src.adapters.cache import StorageNumber, create_client
from src.adapters.cache.repositories import RedisPublicJwkRepository
from src.adapters.filesystem import FileSystem
from src.adapters.filesystem.repositories import FilePrivateJwkRepository
from src.application.jwk import RotateJwk
from src.config import config
from src.scheduler.daemon import JWKRotationDaemon


def get_rotation_daemon() -> JWKRotationDaemon:
    """Собирает демон ротации приватного JWK вместе с его зависимостями.

    Returns:
        JWKRotationDaemon: Готовый к запуску демон ротации.
    """
    repository = RedisPublicJwkRepository(create_client(StorageNumber.KEYS.value))
    key_repository = FilePrivateJwkRepository(FileSystem(config.security.KEY_STORE_DIRECTORY))
    rotate_jwk = RotateJwk(key_repository, repository)

    return JWKRotationDaemon(
        rotate_jwk,
        config.security.KEY_ROTATION_RULE,
        config.security.KEY_OVERWRITE_ON_RESTART,
    )
