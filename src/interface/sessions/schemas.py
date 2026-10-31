from datetime import datetime

from pydantic import BaseModel, Field


class SessionData(BaseModel):
    """Активная сессия пользователя."""

    id: str = Field(description="Идентификатор сессии (`sid`).", examples=["b1f2a3c4d5e6f7a8"])
    current: bool = Field(description="Признак сессии, из которой выполнен запрос.")

    created_at: datetime = Field(description="Момент входа (UTC).")
    expires_at: datetime = Field(description="Момент истечения сессии (UTC).")

    ip: str | None = Field(default=None, description="IP-адрес входа.")
    platform: str | None = Field(default=None, description="Платформа входа (ОС).")
    browser: str | None = Field(default=None, description="Браузер входа.")
    location: str | None = Field(
        default=None, description="Геолокация по IP; зарезервировано, пока не заполняется."
    )


class SessionsList(BaseModel):
    """Список активных сессий пользователя."""

    sessions: list[SessionData] = Field(default_factory=list, description="Активные сессии.")
