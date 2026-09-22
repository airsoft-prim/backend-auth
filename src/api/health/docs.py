from fastapi import status

from src.general.types import RouteDocs

LIVENESS_DOCS: RouteDocs = {
    "summary": "Проверка доступности приложения.",
    "description": (
        "Проверяет факт доступности приложения в данный момент времени. "
        "Если приложение доступно и работает - оно вернёт ответ с кодом 204."
    ),
    "status_code": status.HTTP_204_NO_CONTENT,
    "deprecated": False,
}

READINESS_DOCS: RouteDocs = {
    "summary": "Проверка готовности приложения.",
    "description": (
        "Проверяет факт готовности приложения в данный момент времени. "
        "Приложение считается готовым к использованию, если все компоненты, "
        "такие как База Данных, тоже готовы к работе. Если приложение готово "
        "- оно вернёт ответ с кодом 204."
    ),
    "status_code": status.HTTP_204_NO_CONTENT,
    "deprecated": False,
}
