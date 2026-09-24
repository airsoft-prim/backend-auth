class AuthBackendError(Exception):
    """Ошибка работы Auth Backend'a портала Airsoft Prim."""


class DomainError(AuthBackendError):
    """Ошибка выполнения бизнес-логики."""


class ServiceError(DomainError):
    """Ошибка в работе служб."""


class ProviderError(AuthBackendError):
    """Ошибка выполнения инфраструктурной логики."""


class RepositoryError(ProviderError):
    """Ошибка в работе репозиториев."""
