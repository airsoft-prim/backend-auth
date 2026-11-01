from datetime import timedelta
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecurityConfiguration(BaseSettings):
    """Секция конфигурации безопасности."""

    model_config = SettingsConfigDict(env_prefix="SECURITY_")

    KEY_ROTATION_RULE: str = Field(default="0 3 1 * *")
    KEY_OVERWRITE_ON_RESTART: bool = Field(default=False)
    KEY_STORE_DIRECTORY: Path = Field(default=Path(".keys"))

    ACCESS_TOKEN_TTL: int = Field(default=int(timedelta(minutes=5).total_seconds()), gt=0)
    REFRESH_TOKEN_TTL: int = Field(default=int(timedelta(days=30).total_seconds()), gt=0)
    MAX_ACTIVE_SESSIONS: int = Field(default=5, gt=0)
