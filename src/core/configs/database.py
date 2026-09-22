from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field
from pydantic.networks import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class PathVariadicPostgresDsn(PostgresDsn):
    """Класс PostgresDsn, способный менять путь (имя БД). Необходим для корректной и
    удобной смены имени БД при создании тестовых сессий. При смене пути возвращается
    копия объекта с изменёнными параметрами.
    """

    def change_path(self, value: str) -> PathVariadicPostgresDsn:
        """Копия DSN с другим именем БД.

        Ведущие и хвостовые слэши отбрасываются. Query-параметры,
        fragment, учётные данные и хосты сохраняются как были.
        """
        # Postgres ограничивает идентификатор 63 байтами (NAMEDATALEN - 1).
        # Пробелы и спецсимволы отклоняем явно: без экранирования они молча
        # испортили бы URL. Для тестовых имён (uuid, snake_case) этого достаточно;
        # при необходимости можно ослабить регулярку.
        name_pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,62}$")

        name = value.strip().strip("/")
        if name_pattern.match(name) is None:
            msg = "Invalid database name."
            raise ValueError(msg) from None

        parts = urlsplit(self.unicode_string())
        rebuilt = urlunsplit(parts._replace(path=f"/{name}"))

        return self.__class__(rebuilt)

    @property
    def dbname(self) -> str | None:
        """Имя БД без ведущего слэша. `None` - если БД в DSN не указана."""
        name = (self.path or "").lstrip("/")
        return name or None


class PostgresConfiguration(BaseSettings):
    """Секция конфигурации базы данных."""

    model_config = SettingsConfigDict(env_prefix="DATABASE_")

    HOST: str = Field(default="localhost")
    PORT: int = Field(default=5432, gt=0, le=65_535)
    USER: str = Field(default="username")
    PSWD: str = Field(default="password")
    NAME: str = Field(default="database")

    DRIVER: str = Field(default="asyncpg")

    @property
    def DSN(self) -> PathVariadicPostgresDsn:  # noqa: N802
        """Возвращает провалидированный DSN PostgreSQL."""
        return PathVariadicPostgresDsn.build(
            scheme=f"postgresql+{self.DRIVER}",
            host=self.HOST,
            port=self.PORT,
            username=self.USER,
            password=self.PSWD,
            path=self.NAME,
        )
