from datetime import timedelta
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecurityConfiguration(BaseSettings):
    """Секция конфигурации безопасности.

    Читает настройки ключей, сроков жизни токенов и лимита запросов. Интервалы заданы
    в секундах; лимиты и сроки жизни положительны. `REQUEST_RATE_LIMIT` читается из
    `SUCURITY_REQUEST_RATE_LIMIT`, остальные поля — с префиксом `SECURITY_`.
    """

    model_config = SettingsConfigDict(env_prefix="SECURITY_")

    KEY_ROTATION_RULE: str = Field(default="0 3 1 * *")
    KEY_OVERWRITE_ON_RESTART: bool = Field(default=False)
    KEY_STORE_DIRECTORY: Path = Field(default=Path(".keys"))

    ACCESS_TOKEN_TTL: int = Field(default=int(timedelta(minutes=5).total_seconds()), gt=0)
    REFRESH_TOKEN_TTL: int = Field(default=int(timedelta(days=30).total_seconds()), gt=0)

    REQUEST_RATE_LIMIT: int = Field(
        default=60, gt=0, validation_alias="SUCURITY_REQUEST_RATE_LIMIT"
    )
    REQUEST_RATE_WINDOW: int = Field(default=60, gt=0)
