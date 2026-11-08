"""Конфигурация сервиса из переменных окружения.

Объединяет настройки приложения, PostgreSQL, `Redis`, ключей, токенов, сессий и лимита запросов.

Предоставляет конфигурацию точкам сборки приложения и адаптерам; прикладные сценарии получают
нужные значения через параметры.
"""

from datetime import UTC, datetime
from functools import lru_cache
from typing import Self

from croniter import croniter
from loguru import logger
from pydantic import BaseModel, model_validator

from .app import ApplicationConfiguration
from .cache import CacheConfiguration
from .database import PostgresConfiguration
from .security import SecurityConfiguration

__all__ = ["Configs", "config", "get_app_config"]


class Configs(BaseModel):
    """Конфигурация приложения.

    Объединяет настройки приложения, PostgreSQL, `Redis` и безопасности. Валидатор предупреждает в
    логе, если период ротации ключей короче срока жизни `access`-токена.
    """

    app: ApplicationConfiguration = ApplicationConfiguration()
    cache: CacheConfiguration = CacheConfiguration()
    database: PostgresConfiguration = PostgresConfiguration()
    security: SecurityConfiguration = SecurityConfiguration()

    @model_validator(mode="after")
    def ensure_token_ttl(self) -> Self:
        """Предупреждает о коротком периоде ротации ключей.

        Вычисляет интервал между двумя ближайшими моментами cron-расписания и сравнивает его с
        `ACCESS_TOKEN_TTL`. Несоответствие записывается в лог без отклонения конфигурации.

        Returns:
            Self: Тот же экземпляр конфигурации.
        """
        rotation_clock = croniter(self.security.KEY_ROTATION_RULE, datetime.now(UTC))

        current_rotation_time = rotation_clock.get_next(datetime)
        next_rotation_time = rotation_clock.get_next(datetime)
        rotation_period = int((next_rotation_time - current_rotation_time).total_seconds())

        if rotation_period < self.security.ACCESS_TOKEN_TTL:
            logger.warning("Access token TTL exceeds JWK rotation period.")

        return self


@lru_cache(maxsize=1)
def get_app_config() -> Configs:
    """Возвращает кешированный экземпляр конфигурации.

    Читает окружение при первом вызове. Последующие вызовы используют кеш `lru_cache` до его явной
    очистки.

    Returns:
        Configs: Общая конфигурация приложения.
    """
    return Configs()


config = get_app_config()
