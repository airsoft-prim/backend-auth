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


class UserAlreadyExistsError(ServiceError):
    """Ошибка регистрации: учётная запись с таким username или email уже есть."""


class UserIdentificationError(SecurityError):
    """Ошибка идентификации пользователя."""


class UserAuthenticationError(SecurityError):
    """Ошибка аутентификации пользователя."""


class UserAuthorizationError(SecurityError):
    """Ошибка авторизации: в запросе нет Bearer-токена."""


class JWTEncryptionError(SecurityError):
    """Ошибка выпуска JWT-токена."""


class JWTDecryptionError(SecurityError):
    """Ошибка проверки и чтения JWT-токена."""


class TokenRevokedError(JWTDecryptionError):
    """Ошибка проверки отозванного токена."""


class SessionNotFoundError(ServiceError):
    """Ошибка доступа к сессии: сессии нет или она не принадлежит пользователю."""
