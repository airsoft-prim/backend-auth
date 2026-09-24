from collections.abc import Sequence
from enum import StrEnum


class NiftyStrEnum(StrEnum):
    """StrEnum, удобный для использования в коде и сохранения его значений
    в SQLAlchemy ORM моделях.
    """

    @classmethod
    def values(cls, *_: object) -> Sequence[str]:
        """Значения членов в порядке объявления."""
        return [member.value for member in cls]

    @classmethod
    def names(cls, *_: object) -> Sequence[str]:
        """Имена членов в порядке объявления."""
        return [member.name for member in cls]


class UserRole(NiftyStrEnum):
    """Системная роль пользователя."""

    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"
