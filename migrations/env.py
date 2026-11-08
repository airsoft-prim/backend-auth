import asyncio
from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from src.adapters.database.models import BaseModel

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Forwarding the URI for connecting to the database
presetted = config.get_main_option("sqlalchemy.url", None)
database_uri = os.environ.get("ALEMBIC_URI", None)

if not (database_uri or presetted):
    message = "ALEMBIC_URI is not set"
    raise RuntimeError(message) from None

if database_uri and not presetted:
    config.set_main_option("sqlalchemy.url", database_uri)

target_metadata = BaseModel.metadata


def run_migrations_offline() -> None:
    """Формирует SQL миграций без подключения к PostgreSQL.

    Настраивает Alembic по URL с literal_binds и учётом схем; операции миграций выводятся как SQL в
    offline-режиме.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Выполняет миграции в переданном соединении.

    Args:
        connection (Connection): Синхронное соединение, переданное через `run_sync`.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Выполняет миграции через асинхронный движок.

    Создаёт движок с `NullPool`, передаёт соединение синхронному контексту Alembic и освобождает
    движок после успешного завершения.
    """

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Запускает online-миграции в отдельном цикле событий `asyncio`."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
