from typing import Final

from src.core.configs import config
from src.providers.cache import create_client
from src.providers.cache.repositories import PublicJWKRepository
from src.services.jwk import JWKGenerationService

from .daemon import JWKRotationDaemon

# Отдельная БД для публичных ключей.
KEY_STORE_DB: Final[int] = 1


def get_rotation_daemon() -> JWKRotationDaemon:
    """Собирает демон ротации приватного JWK вместе с его зависимостями.

    Returns:
        JWKRotationDaemon: Готовый к запуску демон ротации.
    """
    repository = PublicJWKRepository(create_client(KEY_STORE_DB))
    jwk_service = JWKGenerationService(config.security.KEY_STORE_DIRECTORY, repository)

    return JWKRotationDaemon(
        jwk_service,
        config.security.KEY_ROTATION_RULE,
        config.security.KEY_OVERWRITE_ON_RESTART,
    )
