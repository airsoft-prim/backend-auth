from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.configs import config
from src.general.security import PASSWORD_HASHER
from src.providers.database import get_session
from src.providers.database.repositories import UserRepository
from src.providers.filesystem import FileSystem
from src.providers.filesystem.repositories import PrivateJWKRepository
from src.services import JWTEncryptionService
from src.services.user import UserService


async def get_user_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserService:
    """Предоставляет сервис учётных записей на время запроса.

    Сессия БД живёт вместе с запросом: коммит делает репозиторий при сохранении.

    Args:
        session (AsyncSession): Асинхронная сессия БД.

    Returns:
        UserService: Сервис учётных записей, привязанный к сессии запроса.
    """
    return UserService(UserRepository(session), hasher=PASSWORD_HASHER)


async def get_encryption_service() -> JWTEncryptionService:
    """Предоставляет сервис выпуска JWT токенов для открытия новой сессии пользователя.

    Returns:
        JWTEncryptionService: Сервис выпуска JWT токенов.
    """

    private_key_repo = PrivateJWKRepository(FileSystem(config.security.KEY_STORE_DIRECTORY))

    return JWTEncryptionService(private_key_repository=private_key_repo)
