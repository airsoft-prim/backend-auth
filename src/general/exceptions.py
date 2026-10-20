class ApplicationError(Exception):
    """Ошибка работы Auth Backend'a портала Airsoft Prim."""


class DomainError(ApplicationError):
    """Ошибка выполнения бизнес-логики."""


class ServiceError(DomainError):
    """Ошибка в работе служб."""


class SecurityError(DomainError):
    """Ошибка безопасности."""


class ProviderError(ApplicationError):
    """Ошибка выполнения инфраструктурной логики."""


class RepositoryError(ProviderError):
    """Ошибка в работе репозиториев."""
