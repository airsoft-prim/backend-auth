from sqlalchemy import Select, func, select

from src.providers.database.models import User

from ._base import DatabaseRepository


class UserRepository(DatabaseRepository[User]):
    """Репозиторий учётных записей портала."""

    model = User

    async def get_by_username(self, username: str) -> User | None:
        """Возвращает учётную запись по логину.

        Логин уникален регистрозависимо (`UNIQUE` по `username`), поэтому и поиск
        точный: `docs/DOMAIN.md` §7.2.

        Args:
            username (str): Логин учётной записи.

        Raises:
            RepositoryError: Если обращение к БД завершилось ошибкой.

        Returns:
            User | None: Учётная запись или None, если логин ещё свободен.
        """
        statement: Select[tuple[User]] = select(User).where(User.username == username)

        return await self._acquire(statement)

    async def get_by_email(self, email: str) -> User | None:
        """Возвращает учётную запись по адресу электронной почты.

        Регистр адреса не учитывается — как и уникальность email в БД, которую держит
        функциональный индекс по `lower(email)`.

        Args:
            email (str): Адрес электронной почты учётной записи.

        Raises:
            RepositoryError: Если обращение к БД завершилось ошибкой.

        Returns:
            User | None: Учётная запись или None, если адрес ещё свободен.
        """
        statement: Select[tuple[User]] = select(User).where(func.lower(User.email) == email.lower())

        return await self._acquire(statement)

    async def _acquire(self, statement: Select[tuple[User]]) -> User | None:
        """Выполняет выборку единственной учётной записи.

        Args:
            statement (Select[tuple[User]]): Запрос выборки учётной записи.

        Raises:
            RepositoryError: Если обращение к БД завершилось ошибкой.

        Returns:
            User | None: Найденная учётная запись или None, если её нет.
        """
        with self._as_repository_error("User getting error."):
            result = await self._session.execute(statement)

        return result.scalars().first()
