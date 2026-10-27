from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters._base import Repository
from src.adapters.database.models import UserModel
from src.domain.entities import User


def _user_from_model(model: UserModel) -> User:
    """Преобразует ORM-модель учётной записи в доменную сущность.

    Args:
        model (UserModel): Строка таблицы `auth.users`.

    Returns:
        User: Доменная сущность учётной записи.
    """
    return User(
        id=model.id,
        username=model.username,
        email=model.email,
        pswd_hash=model.pswd_hash,
        system_role=model.system_role,
        disabled=model.disabled,
        last_pswd_change=model.last_pswd_change,
        disabled_at=model.disabled_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _user_to_model(user: User) -> UserModel:
    """Преобразует доменную сущность в ORM-модель для сохранения.

    Идентификатор и метки времени новая запись не несёт: их проставляет БД.

    Args:
        user (User): Доменная сущность учётной записи.

    Returns:
        UserModel: ORM-модель, готовая к сохранению.
    """
    model = UserModel(
        username=user.username,
        email=user.email,
        pswd_hash=user.pswd_hash,
        system_role=user.system_role,
        disabled=user.disabled,
        last_pswd_change=user.last_pswd_change,
        disabled_at=user.disabled_at,
    )

    if user.id is not None:
        model.id = user.id

    return model


class SqlAlchemyUserRepository(Repository):
    """Репозиторий учётных записей поверх PostgreSQL.

    Адаптер порта `UserRepository`: доменная сущность `User` отдаётся наружу,
    а в БД ходит ORM-модель `UserModel`.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Инициализация класса.

        Args:
            session (AsyncSession): Асинхронная сессия БД.
        """
        self._session = session

    async def get(self, user_id: int) -> User | None:
        """Возвращает учётную запись по её идентификатору.

        Args:
            user_id (int): Идентификатор учётной записи.

        Raises:
            RepositoryError: Если обращение к БД завершилось ошибкой.

        Returns:
            User | None: Учётная запись или None, если её нет.
        """
        model = await self._session.get(UserModel, user_id)

        return _user_from_model(model) if model is not None else None

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
        statement: Select[tuple[UserModel]] = select(UserModel).where(
            UserModel.username == username
        )

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
        statement: Select[tuple[UserModel]] = select(UserModel).where(
            func.lower(UserModel.email) == email.lower()
        )

        return await self._acquire(statement)

    async def save(self, user: User) -> None:
        """Сохраняет учётную запись в БД.

        Args:
            user (User): Учётная запись для сохранения.

        Raises:
            RepositoryError: Если обращение к БД завершилось ошибкой.
        """
        self._session.add(_user_to_model(user))

        with self._as_repository_error("User saving error."):
            await self._session.commit()

    async def _acquire(self, statement: Select[tuple[UserModel]]) -> User | None:
        """Выполняет выборку единственной учётной записи.

        Args:
            statement (Select[tuple[UserModel]]): Запрос выборки учётной записи.

        Raises:
            RepositoryError: Если обращение к БД завершилось ошибкой.

        Returns:
            User | None: Найденная учётная запись или None, если её нет.
        """
        with self._as_repository_error("User getting error."):
            result = await self._session.execute(statement)

        model = result.scalars().first()

        return _user_from_model(model) if model is not None else None
