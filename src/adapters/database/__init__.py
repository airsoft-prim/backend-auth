"""Подключение и ORM-модели PostgreSQL.

Объединяет асинхронный движок, фабрику сессий, метаданные и модели учётных записей.

Служит основой SQLAlchemy-репозиториев и источником метаданных для Alembic.
"""

from .engine import engine
from .models import BaseModel, TimestampedModel, UserModel
from .session import async_session, get_session

__all__ = [
    "BaseModel",
    "TimestampedModel",
    "UserModel",
    "async_session",
    "engine",
    "get_session",
]
