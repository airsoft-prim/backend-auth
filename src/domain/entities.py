from dataclasses import dataclass
from datetime import datetime

from src.domain.enums import UserRole


@dataclass(slots=True)
class User:
    """Учётная запись портала: доменная сущность без привязки к хранилищу.

    Метки времени, идентификатор и роль по умолчанию проставляет слой хранения
    (`infrastructure`), поэтому у новой записи они ещё пусты.
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
