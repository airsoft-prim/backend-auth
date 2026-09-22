from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApplicationConfiguration(BaseSettings):
    """Секция конфигурации основных настроек приложения."""

    model_config = SettingsConfigDict(env_prefix="APP_")

    NAME: str = Field(default="Airsoft-Prim | Auth Server")
    DEBUG: bool = Field(default=False)
