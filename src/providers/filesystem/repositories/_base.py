from contextlib import suppress

from src.providers import Repository
from src.providers.filesystem import FileSystem


class FileRepository(Repository):
    """Репозиторий одного файла в файловой системе."""

    FILE_NAME: str

    def __init__(self, file_system: FileSystem) -> None:
        """Инициализация класса.

        Args:
            file_system (FileSystem): Объект доступа к файловой системе.
        """
        self._file_system = file_system

    async def acquire(self) -> bytes | None:
        """Читает файл репозитория.

        Raises:
            RepositoryError: Если файл не читается.

        Returns:
            bytes | None: Содержимое файла или None, если файла нет.
        """
        with self._as_repository_error(f"File {self.FILE_NAME!r} reading error."):
            with suppress(FileNotFoundError):
                return await self._file_system.read(self.FILE_NAME)

            return None

    async def store(self, payload: bytes) -> None:
        """Записывает файл репозитория.

        Args:
            payload (bytes): Содержимое файла.

        Raises:
            RepositoryError: Если файл не пишется.
        """
        with self._as_repository_error(f"File {self.FILE_NAME!r} writing error."):
            await self._file_system.write(self.FILE_NAME, payload)
