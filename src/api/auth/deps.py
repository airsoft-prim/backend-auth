from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.general.security import PASSWORD_HASHER
from src.providers.database import get_session
from src.providers.database.repositories import UserRepository
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
