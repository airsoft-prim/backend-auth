from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field, SecretStr

from src.api.auth.schemas import PASSWORD_REQUIREMENTS


def check_password_policy(value: SecretStr) -> SecretStr:
    """Проверяет пароль по требованиям безопасности.

    Требования — политика пароля из `docs/DOMAIN.md` §7. Шаблон
    `PASSWORD_REQUIREMENTS` общий с регистрацией: политика живёт в одном месте.

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


NewPassword = Annotated[SecretStr, AfterValidator(check_password_policy)]


class ChangePasswordRequestBody(BaseModel):
    """Тело запроса на смену пароля."""

    current_password: SecretStr = Field(description="Текущий пароль УЗ.")
    new_password: NewPassword = Field(min_length=8, max_length=72, description="Новый пароль УЗ.")


class PasswordResetRequestBody(BaseModel):
    """Тело запроса на сброс пароля."""

    email: EmailStr = Field(description="Адрес электронной почты.", examples=["user@example.ru"])


class PasswordResetConfirmRequestBody(BaseModel):
    """Тело запроса на подтверждение сброса пароля."""

    token: str = Field(description="Одноразовый токен из ссылки в письме.")
    new_password: NewPassword = Field(min_length=8, max_length=72, description="Новый пароль УЗ.")
