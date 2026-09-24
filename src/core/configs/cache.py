from __future__ import annotations

from pydantic import Field
from pydantic.networks import RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class CacheConfiguration(BaseSettings):
    """Секция конфигурации кеша."""

    model_config = SettingsConfigDict(env_prefix="CACHE_")

    DB: int = Field(default=0, ge=0)
    HOST: str = Field(default="localhost")
    PORT: int = Field(default=6379, gt=0, le=65_535)
    USER: str | None = Field(default=None)
    PSWD: str | None = Field(default=None)

    MAX_CONNECTIONS: int = Field(default=20)

    @property
    def DSN(self) -> RedisDsn:  # noqa: N802
        """Возвращает провалидированный DSN Redis."""
        return RedisDsn.build(
            scheme="redis",
            username=self.USER,
            password=self.PSWD,
            host=self.HOST,
            port=self.PORT,
            path=str(self.DB),
        )
