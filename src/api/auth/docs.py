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
        "Проверяет логин и пароль и выдаёт Токен доступа на 24 часа. Заблокированной "
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
