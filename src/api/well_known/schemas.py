from typing import Any

from pydantic import BaseModel, Field


class JSONWebKeySet(BaseModel):
    """Модель ответа на запрос JWKS."""

    keys: list[Any] = Field(default_factory=list)
