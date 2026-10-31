from fastapi import status

from src.interface._utils import RouteDocs

JWKS_DOCS: RouteDocs = {
    "summary": "Получение публичных ключей подписи токенов.",
    "description": (
        "Возвращает набор публичных ключей (JWKS) в формате RFC 7517. "
        "Ключи используются сторонними сервисами для проверки подписи "
        "токенов, выданных сервером аутентификации."
    ),
    "status_code": status.HTTP_200_OK,
    "deprecated": False,
}
