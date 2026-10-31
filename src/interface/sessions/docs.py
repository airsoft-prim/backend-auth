from fastapi import status

from src.interface._utils import RouteDocs

LIST_SESSIONS_DOCS: RouteDocs = {
    "summary": "Список активных сессий.",
    "description": (
        "Возвращает активные сессии владельца refresh-токена: момент входа, срок действия, "
        "IP-адрес и разобранный User-Agent (платформа и браузер). Поле `location` "
        "зарезервировано под геолокацию по IP и пока не заполняется."
    ),
    "status_code": status.HTTP_200_OK,
    "deprecated": False,
}

CLOSE_SESSION_DOCS: RouteDocs = {
    "summary": "Закрытие выбранной сессии.",
    "description": (
        "Отзывает выбранную сессию (`sid`) владельца refresh-токена: все токены этой сессии "
        "становятся недействительными."
    ),
    "status_code": status.HTTP_204_NO_CONTENT,
    "deprecated": False,
}

CLOSE_OTHER_SESSIONS_DOCS: RouteDocs = {
    "summary": "Закрытие всех сессий, кроме текущей.",
    "description": (
        "Отзывает все активные сессии владельца refresh-токена, кроме сессии, из которой "
        "выполнен запрос."
    ),
    "status_code": status.HTTP_204_NO_CONTENT,
    "deprecated": False,
}
