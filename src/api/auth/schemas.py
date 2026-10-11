from datetime import datetime
import re
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

from src.general.enums import UserRole

# Классы символов политики пароля в нотации ASCII.
# Пароль должен содержать хотя бы один(ну): Спец. символ, заглавную и строчную буквы, цифру.
# Диапазон [^\w\s] позволяет не захватывать символы вне ASCII (напр. Эмодзи).
PASSWORD_REQUIREMENTS: Final[re.Pattern[str]] = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])(?=.*[!-/:-@\[-`{-~])",
    re.DOTALL,
)

# Политика username общая для регистрации и входа.
Username = Annotated[
    str,
    Field(
        min_length=3,
        max_length=30,
        pattern=r"^[A-Za-z][A-Za-z0-9_-]*$",
        description="Логин учётной записи.",
        examples=["Oidaho"],
    ),
]


class RegisterRequestBody(BaseModel):
    """Тело запроса на регистрацию пользователя."""

    username: Username
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
    """Тело запроса на вход в систему."""

    username: Username
    password: SecretStr = Field(description="Пароль учётной записи.")


class AccessToken(BaseModel):
    """Ответ на успешный вход в систему с выпущенным токеном доступа.

    Набор полей обоснован соглашением RFC 6749 §5.1.
    """

    access_token: str = Field(description="JWT токен доступа.")
    token_type: Literal["Bearer"] = Field(default="Bearer", description="Тип токена")

    expires_in: int = Field(description="Временная метка инвалидации токена.")


class UserData(BaseModel):
    """Данные учётной записи, который сервис сообщает её владельцу."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Идентификатор учётной записи.", examples=[42])

    username: str = Field(description="Логин учётной записи.", examples=["Oidaho"])
    email: EmailStr = Field(description="Адрес электронной почты.", examples=["user@example.ru"])
    role: UserRole = Field(description="Системная роль владельца учётной записи.")

    created_at: datetime = Field(description="Момент создания учётной записи.")
    updated_at: datetime = Field(description="Момент последнего обновления учётной записи.")
