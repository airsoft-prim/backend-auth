from ._base import FileRepository


class FilePrivateJwkRepository(FileRepository):
    """Репозиторий приватного ключа подписи в keyfile."""

    FILE_NAME: str = "private-jwk.pem"
