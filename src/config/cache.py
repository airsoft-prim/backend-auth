from __future__ import annotations

from typing import TypedDict

from pydantic import Field
from pydantic.networks import RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class RedisCredentials(TypedDict, total=False):
    """Необязательные параметры аутентификации Redis."""

    username: str
    password: str


class CacheConfiguration(BaseSettings):
    """Секция конфигурации кеша.

    Читает переменные с префиксом `CACHE_` и формирует `RedisDsn`. Проверяет диапазон порта и
    неотрицательный номер логической БД; учётные данные могут отсутствовать.
    """

    model_config = SettingsConfigDict(env_prefix="CACHE_")

    DB: int = Field(default=0, ge=0)
    HOST: str = Field(default="localhost")
    PORT: int = Field(default=6379, gt=0, le=65_535)
    USER: str | None = Field(default=None)
    PSWD: str | None = Field(default=None)

    @property
    def credentials(self) -> RedisCredentials | None:
        """Возвращает учётные данные Redis или `None`, если они не заданы."""
        if self.USER is not None and self.PSWD is not None:
            return {"username": self.USER, "password": self.PSWD}

        return None

    @property
    def DSN(self) -> RedisDsn:  # noqa: N802
        """Возвращает провалидированный `DSN` `Redis`."""
        return RedisDsn.build(
            scheme="redis",
            username=self.USER,
            password=self.PSWD,
            host=self.HOST,
            port=self.PORT,
            path=str(self.DB),
        )
