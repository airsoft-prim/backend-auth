from fastapi import status

from src.general.types import RouteDocs

REGISTER_DOCS: RouteDocs = {
    "summary": "Регистрация пользователя.",
    "description": (
        "Создаёт учётную запись портала. Проверяются уникальность username и email "
        "(email — регистронезависимо) и политики username и пароля. Пароль "
        "сохраняется в виде bcrypt-хеша, новой учётной записи назначается роль `user`. "
        "Подтверждение email не требуется."
    ),
    "status_code": status.HTTP_201_CREATED,
    "deprecated": False,
}

LOGIN_DOCS: RouteDocs = {
    "summary": "Вход в систему.",
    "description": (
        "Проверяет email и пароль и выдаёт access-токен на 24 часа. Заблокированной "
        "учётной записи во входе отказывается. Сообщение об ошибке не раскрывает, "
        "существует ли учётная запись и что именно не совпало."
    ),
    "status_code": status.HTTP_200_OK,
    "deprecated": False,
}

LOGOUT_DOCS: RouteDocs = {
    "summary": "Выход из системы.",
    "description": (
        "Завершает сессию пользователя. Пока выданные токены не отзываются, выход "
        "означает удаление токена на стороне клиента: тот же токен остаётся "
        "действительным до истечения срока жизни. Отзыв через Redis — планируется."
    ),
    "status_code": status.HTTP_204_NO_CONTENT,
    "deprecated": False,
}
