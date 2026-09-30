from collections.abc import Sequence
from typing import Any, overload
from uuid import UUID

from sqlalchemy import ColumnElement, delete as delete_, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from src.providers import Repository

type EntityID = UUID | int


class DatabaseRepository[D: DeclarativeBase](Repository):
    """Репозиторий для взаимодействия с сущностями в БД."""

    model: type[D]

    def __init__(self, session: AsyncSession) -> None:
        """Инициализация класса.

        Args:
            session (AsyncSession): Асинхронная сессия БД.
        """
        self._session = session

    # ! Не поддерживает составные ключи
    @staticmethod
    def _id_column(model: type[D]) -> ColumnElement[Any]:
        """Колонка первичного ключа модели: запросы не зависят
        от имени и типа колонки первичного ключа.

        Args:
            model (type[D]): ORM модель сущности.

        Returns:
            ColumnElement[Any]: Колонка первичного ключа модели в БД.
        """
        return inspect(model).primary_key[0]

    @overload
    async def get(self, id_: EntityID) -> D | None: ...

    @overload
    async def get(self, id_: Sequence[EntityID]) -> list[D] | None: ...

    async def get(self, id_: EntityID | Sequence[EntityID]) -> D | list[D] | None:
        """Метод получения сущности или списка сущностей из БД
        по их идентификатору.

        Args:
            id_ (EntityID | Sequence[EntityID]): Идентификатор или список
                идентификаторов сущностей в БД.

        Returns:
            D | list[D] | None: ORM модель при запросе по одному
                идентификатору, список моделей - при запросе по списку
                идентификаторов. None - если записи не найдены.
        """
        id_column = self._id_column(self.model)
        stmt = select(self.model).where(
            (id_column.in_(id_)) if isinstance(id_, Sequence) else (id_column == id_)
        )

        with self._as_repository_error(f"{self.model.__name__} getting error."):
            result = await self._session.execute(stmt)
            rows = list(result.scalars().all())

        if not rows:
            return None

        return rows if isinstance(id_, Sequence) else rows[0]

    @overload
    async def save(self, entity: D) -> None: ...

    @overload
    async def save(self, entity: Sequence[D]) -> None: ...

    async def save(self, entity: D | Sequence[D]) -> None:
        """Метод сохранения сущности или списка сущностей в БД.

        Args:
            entity (D | Sequence[D]): Сущность или список сущностей
                для сохранения.
        """
        if isinstance(entity, Sequence):
            self._session.add_all(entity)

        else:
            self._session.add(entity)

        with self._as_repository_error(f"{self.model.__name__} saving error."):
            await self._session.commit()

    @overload
    async def delete(self, id_: EntityID) -> None: ...

    @overload
    async def delete(self, id_: Sequence[EntityID]) -> None: ...

    async def delete(self, id_: EntityID | Sequence[EntityID]) -> None:
        """Метод удаления сущности или списка сущностей из БД
        по их идентификатору.

        Args:
            entity (EntityID | Sequence[EntityID]): Идентификатор или список
                идентификаторов сущностей в БД.
        """
        id_column = self._id_column(self.model)
        stmt = delete_(self.model).where(
            (id_column.in_(id_)) if isinstance(id_, Sequence) else (id_column == id_)
        )

        with self._as_repository_error(f"{self.model.__name__} deleting error."):
            await self._session.execute(stmt)
            await self._session.commit()
