from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApplicationConfiguration(BaseSettings):
    """Секция конфигурации основных настроек приложения."""

    model_config = SettingsConfigDict(env_prefix="APP_")

    NAME: str = Field(default="Auth Server")
    PROJECT: str = Field(default="Airsoft Prim")

    DEBUG: bool = Field(default=False)
