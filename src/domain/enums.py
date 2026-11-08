from collections.abc import Sequence
from enum import StrEnum


class NiftyStrEnum(StrEnum):
    """Строковое перечисление с выборкой имён и значений.

    Предоставляет имена и строковые значения членов в порядке объявления. Метод `values`
    используется SQLAlchemy при сохранении перечислений.
    """

    @classmethod
    def values(cls, *_: object) -> Sequence[str]:
        """Значения членов в порядке объявления.

        Args:
            *_ (object): Неиспользуемые аргументы вызывающего кода.

        Returns:
            Sequence[str]: Значения членов перечисления в порядке объявления.
        """
        return [member.value for member in cls]

    @classmethod
    def names(cls, *_: object) -> Sequence[str]:
        """Имена членов в порядке объявления.

        Args:
            *_ (object): Неиспользуемые аргументы вызывающего кода.

        Returns:
            Sequence[str]: Имена членов перечисления в порядке объявления.
        """
        return [member.name for member in cls]


class UserRole(NiftyStrEnum):
    """Системная роль пользователя.

    Определяет значения `admin`, `moderator` и `user` для роли учётной записи и claim `srl`
    `access`- токена.
    """

    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"


class TokenType(NiftyStrEnum):
    """Тип JWT токена.

    Различает `access`- и `refresh`-токены при формировании заголовка `typ` и ключей маркеров
    отзыва.
    """

    ACCESS = "access"
    REFRESH = "refresh"
