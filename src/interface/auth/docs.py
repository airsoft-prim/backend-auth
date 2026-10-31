from fastapi import status

from src.interface._utils import RouteDocs

REGISTER_DOCS: RouteDocs = {
    "summary": "Регистрация пользователя.",
    "description": "Создаёт учётную запись портала. Подтверждение email не требуется.",
    "status_code": status.HTTP_204_NO_CONTENT,
    "deprecated": False,
}

LOGIN_DOCS: RouteDocs = {
    "summary": "Вход в систему.",
    "description": (
        "Проверяет логин и пароль и выдаёт access-токен (24 часа по умолчанию), а "
        "refresh-токен (30 дней по умолчанию) кладёт в HTTP-only cookie. Оба токена "
        "связаны идентификатором сессии `sid`. Заблокированной учётной записи во входе "
        "отказывается. Сообщение об ошибке не раскрывает, существует ли учётная запись и "
        "что именно не совпало."
    ),
    "status_code": status.HTTP_200_OK,
    "deprecated": False,
}

REFRESH_DOCS: RouteDocs = {
    "summary": "Обновление access-токена.",
    "description": (
        "Принимает refresh-токен из HTTP-only cookie и выдаёт новый access-токен той же "
        "сессии (`sid`). Старый refresh-токен отзывается (ротация), а роль перечитывается "
        "из БД."
    ),
    "status_code": status.HTTP_200_OK,
    "deprecated": False,
}

LOGOUT_DOCS: RouteDocs = {
    "summary": "Выход из системы.",
    "description": (
        "Проверяет refresh-токен из HTTP-only cookie и отзывает сессию (`sid`) в Redis. "
        "Все токены сессии становятся недействительными, а cookie удаляется."
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
