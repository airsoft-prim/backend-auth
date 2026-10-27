from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, NotRequired, TypedDict

from src.domain.enums import UserRole


class AccessTokenClaims(TypedDict, total=True):
    """Claims access-токена, которые сервис выпускает и проверяет.

    Каждый атрибут аннотирован согласно RFC 7519.
    """

    iss: Annotated[str, "Issuer"]
    sub: Annotated[str, "Subject"]
    aud: Annotated[str, "Audience"]
    exp: Annotated[int, "Expiration time"]
    iat: Annotated[int, "Issued at"]
    jti: Annotated[str, "JWT ID"]

    # Кастомный необязательный claim: роль есть не у всех потребителей.
    srl: NotRequired[Annotated[str, "Subject Role"]]


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
