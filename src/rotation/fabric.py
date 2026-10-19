from src.core.configs import config
from src.providers.cache import StorageNumber, create_client
from src.providers.cache.repositories import PublicJWKRepository
from src.providers.filesystem import FileSystem
from src.providers.filesystem.repositories import PrivateJWKRepository
from src.services.jwk import JWKGenerationService

from .daemon import JWKRotationDaemon


def get_rotation_daemon() -> JWKRotationDaemon:
    """Собирает демон ротации приватного JWK вместе с его зависимостями.

    Returns:
        JWKRotationDaemon: Готовый к запуску демон ротации.
    """
    repository = PublicJWKRepository(create_client(StorageNumber.KEYS.value))
    key_repository = PrivateJWKRepository(FileSystem(config.security.KEY_STORE_DIRECTORY))
    jwk_service = JWKGenerationService(key_repository, repository)

    return JWKRotationDaemon(
        jwk_service,
        config.security.KEY_ROTATION_RULE,
        config.security.KEY_OVERWRITE_ON_RESTART,
    )
