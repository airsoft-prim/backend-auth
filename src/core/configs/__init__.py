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


class Configs(BaseModel):
    """Конфигурация приложения."""

    app: ApplicationConfiguration = ApplicationConfiguration()
    cache: CacheConfiguration = CacheConfiguration()
    database: PostgresConfiguration = PostgresConfiguration()
    security: SecurityConfiguration = SecurityConfiguration()

    @model_validator(mode="after")
    def ensure_token_ttl(self) -> Self:
        """Проверяет согласованность периода ротации ключей со временем жизни токена.

        Период ротации считается по cron-правилу `SECURITY_KEY_ROTATION_RULE`: берутся два
        ближайших момента ротации, а их разница принимается за период, в течение которого
        публичный ключ прошлой генерации остаётся в наборе JWKS.

        Returns:
            Self: Проверенная конфигурация приложения.
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
    """Метод, предоставляющий конфигурацию приложения.

    Удобен для использования внутри FastAPI Dependencies.

    Returns:
        Configs: Конфигурация приложения.
    """
    return Configs()


config = get_app_config()
