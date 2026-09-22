from functools import lru_cache

from pydantic import BaseModel

from .app import ApplicationConfiguration


class Configs(BaseModel):
    """Конфигурация приложения."""

    app: ApplicationConfiguration = ApplicationConfiguration()


@lru_cache
def get_app_config() -> Configs:
    """Метод, предоставляющий конфигурацию приложения.

    Удобен для использования внутри FastAPI Dependencies.

    Returns:
        Configs: Конфигурация приложения.
    """
    return Configs()


config = get_app_config()
