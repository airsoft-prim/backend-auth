from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .engine import engine

async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Возвращает асинхронную сессию подключения к БД.

    Yields:
        AsyncGenerator[AsyncSession]: Асинхронная сессия БД.
    """
    async with async_session() as session:
        yield session
