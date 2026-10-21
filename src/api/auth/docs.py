from fastapi import status

from src.general.types import RouteDocs

REGISTER_DOCS: RouteDocs = {
    "summary": "Регистрация пользователя.",
    "description": "Создаёт учётную запись портала. Подтверждение email не требуется.",
    "status_code": status.HTTP_204_NO_CONTENT,
    "deprecated": False,
}

LOGIN_DOCS: RouteDocs = {
    "summary": "Вход в систему.",
    "description": (
        "Проверяет логин и пароль и выдаёт токен доступа. Время жизни — "
        "SECURITY_ACCESS_TOKEN_TTL (24 часа по умолчанию). Заблокированной учётной "
        "записи во входе отказывается. Сообщение об ошибке не раскрывает, существует ли "
        "учётная запись и что именно не совпало."
    ),
    "status_code": status.HTTP_200_OK,
    "deprecated": False,
}

LOGOUT_DOCS: RouteDocs = {
    "summary": "Выход из системы.",
    "description": (
        "Проверяет Bearer-токен и помещает его `jti` в Redis до истечения срока "
        "действия токена. Повторный выход с отозванным токеном отклоняется."
    ),
    "status_code": status.HTTP_204_NO_CONTENT,
    "deprecated": False,
}

ME_DOCS: RouteDocs = {
    "summary": "Профиль владельца токена.",
    "description": (
        "Проверяет Bearer-токен, находит учётную запись по `sub` и возвращает её данные "
        "без хеша пароля и служебных признаков."
    ),
    "status_code": status.HTTP_200_OK,
    "deprecated": False,
}
