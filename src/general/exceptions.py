class AuthBackendError(Exception):
    """Ошибка работы Auth Backend'a портала Airsoft Prim."""


class DomainError(AuthBackendError):
    """Ошибка выполнения бизнес-логики."""
