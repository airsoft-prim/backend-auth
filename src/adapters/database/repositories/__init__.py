"""Репозитории учётных записей в PostgreSQL.

Отображает ORM-модели в доменные сущности и выполняет поиск и сохранение пользователей.

Реализует `UserRepository` для сценариев регистрации, входа и чтения профиля.
"""

from .user import SqlAlchemyUserRepository

__all__ = ["SqlAlchemyUserRepository"]
