from dataclasses import dataclass
from datetime import datetime

from src.domain.enums import UserRole


@dataclass(slots=True)
class User:
    """Учётная запись портала.

    Содержит логин, почту, хеш пароля и состояние учётной записи. Роль новой сущности — `user`;
    идентификатор и временные метки могут быть `None` до загрузки из хранилища.
    """

    username: str
    email: str
    pswd_hash: str

    system_role: UserRole = UserRole.USER
    disabled: bool = False

    id: int | None = None
    last_pswd_change: datetime | None = None
    disabled_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# TODO: Добавить геолокацию.


@dataclass(slots=True)
class Session:
    """Сессия пользователя.

    Связывает `access`- и `refresh`-токены через `id`, передаваемый в claim `sid`. Содержит
    владельца, срок действия, метку отзыва и доступный контекст входа. Поле `location`
    зарезервировано для геолокации и при создании сессии не заполняется.
    """

    id: str
    user_id: int

    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None

    ip: str | None = None
    user_agent: str | None = None
    platform: str | None = None
    browser: str | None = None
    location: str | None = None
