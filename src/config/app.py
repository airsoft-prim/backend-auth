from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApplicationConfiguration(BaseSettings):
    """Секция конфигурации основных настроек приложения.

    Читает переменные с префиксом `APP_`. Задаёт имя сервиса и проекта, режим отладки `DEBUG` и
    независимое включение документации `DOCS`.
    """

    model_config = SettingsConfigDict(env_prefix="APP_")

    NAME: str = Field(default="Auth Server")
    PROJECT: str = Field(default="Airsoft Prim")

    DEBUG: bool = Field(default=False)
    DOCS: bool = Field(default=False)
