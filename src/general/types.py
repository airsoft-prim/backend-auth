from enum import Enum
from typing import Any, TypedDict


class RouteDocs(TypedDict, total=False):
    """Формат документирующих данных к пути API."""

    summary: str
    operation_id: str
    description: str
    deprecated: bool
    tags: list[str | Enum]
    status_code: int
    response_description: str
    responses: dict[int | str, dict[str, Any]] | None
