from datetime import datetime
import re
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

from src.domain.enums import UserRole

# Классы символов политики пароля в нотации ASCII.
# Пароль должен содержать хотя бы один(ну): Спец. символ, заглавную и строчную буквы, цифру.
# Диапазон [^\w\s] позволяет не захватывать символы вне ASCII (напр. Эмодзи).
PASSWORD_REQUIREMENTS: Final[re.Pattern[str]] = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])(?=.*[!-/:-@\[-`{-~])",
    re.DOTALL,
)

# Политика username общая для регистрации и входа, меняться не должна!
Username = Annotated[
    str,
    Field(min_length=3, max_length=30, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$"),
]


class RegisterRequestBody(BaseModel):
    """Тело запроса на регистрацию пользователя.

    Проверяет формат логина, адрес почты, длину пароля `8`–`72` символа и наличие требуемых классов
    символов. Пароль представлен `SecretStr`.
    """

    username: Username = Field(description="Логин учётной записи.", examples=["Oidaho"])
    email: EmailStr = Field(description="Адрес электронной почты.", examples=["user@example.ru"])
    password: SecretStr = Field(min_length=8, max_length=72, description="Пароль учётной записи.")

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: SecretStr) -> SecretStr:
        """Проверяет, что пароль соответствует требованиям безопасности.

        Args:
            value (SecretStr): Пароль из тела запроса.

        Returns:
            SecretStr: Пароль без изменений, если проверка пройдена.

        Raises:
            ValueError: Пароль не соответствует требованиям безопасности.
        """
        if PASSWORD_REQUIREMENTS.match(value.get_secret_value()) is None:
            msg = "Password does not meet the security requirements."
            raise ValueError(msg)

        return value


class LoginRequestBody(BaseModel):
    """Тело запроса на вход в систему.

    Проверяет формат логина и принимает пароль как `SecretStr`. Соответствие пароля сохранённому
    хешу проверяется в `LoginUser`.
    """

    username: Username = Field(description="Логин учётной записи.", examples=["Oidaho"])
    password: SecretStr = Field(description="Пароль учётной записи.")


class AccessToken(BaseModel):
    """Ответ с выпущенным `access`-токеном.

    Возвращается при обновлении токенов и содержит `access_token`, `token_type` и `expires_in` в
    секундах. Refresh-токен передаётся отдельно в HTTP-only cookie.
    """

    access_token: str = Field(description="JWT токен доступа.")
    token_type: Literal["Bearer"] = Field(default="Bearer", description="Тип токена")

    expires_in: int = Field(description="Срок жизни токена в секундах.")


class UserData(BaseModel):
    """Данные учётной записи, который сервис сообщает её владельцу.

    Сериализует идентификатор, логин, почту, роль и временные метки из атрибутов сущности. Поле
    `role` читает `system_role`; хеш пароля в ответ не входит.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int = Field(description="Идентификатор учётной записи.", examples=[42])

    username: str = Field(description="Логин учётной записи.", examples=["Oidaho"])
    email: EmailStr = Field(description="Адрес электронной почты.", examples=["user@example.ru"])
    role: UserRole = Field(
        validation_alias="system_role", description="Системная роль владельца учётной записи."
    )

    created_at: datetime = Field(description="Момент создания учётной записи.")
    updated_at: datetime = Field(description="Момент последнего обновления учётной записи.")
