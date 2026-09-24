from fastapi import status

from src.general.types import RouteDocs

CHANGE_PASSWORD_DOCS: RouteDocs = {
    "summary": "Смена пароля.",
    "description": (
        "Меняет пароль учётной записи: пользователь подтверждает текущий пароль и задаёт "
        "новый по политике. Обновляются хеш пароля и дата его последней смены. Уже "
        "выданные токены остаются действительными до истечения срока жизни."
    ),
    "status_code": status.HTTP_204_NO_CONTENT,
    "deprecated": False,
}

START_PASSWORD_RESET_DOCS: RouteDocs = {
    "summary": "Запрос на сброс пароля.",
    "description": (
        "Принимает email учётной записи и запускает сброс: сервис заводит в Redis "
        "временную запись об активном сбросе и отправляет письмо со ссылкой на страницу "
        "сброса. Ответ одинаков и для существующей, и для неизвестной учётной записи, "
        "чтобы не раскрывать, зарегистрирован ли адрес."
    ),
    "status_code": status.HTTP_204_NO_CONTENT,
    "deprecated": False,
}

CONFIRM_PASSWORD_RESET_DOCS: RouteDocs = {
    "summary": "Подтверждение сброса пароля.",
    "description": (
        "Принимает одноразовый токен из ссылки в письме и новый пароль: проверяет запись "
        "об активном сбросе и устанавливает пароль по политике. Токен одноразовый: после "
        "успешного подтверждения он больше не принимается."
    ),
    "status_code": status.HTTP_204_NO_CONTENT,
    "deprecated": False,
}
