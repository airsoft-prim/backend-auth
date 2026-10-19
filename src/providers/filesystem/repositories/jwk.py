from ._base import FileRepository


class PrivateJWKRepository(FileRepository):
    """Репозиторий приватного ключа подписи в keyfile."""

    FILE_NAME: str = "private-jwk.pem"
