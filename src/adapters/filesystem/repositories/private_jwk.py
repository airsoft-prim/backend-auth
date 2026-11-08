from ._base import FileRepository


class FilePrivateJwkRepository(FileRepository):
    """Репозиторий приватного ключа подписи в keyfile.

    Хранит байты приватного ключа в файле `private-jwk.pem` относительно корня `FileSystem`. Формат
    ключа интерпретируют сценарии подписи и ротации.
    """

    FILE_NAME: str = "private-jwk.pem"
