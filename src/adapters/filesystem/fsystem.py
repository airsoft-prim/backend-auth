import asyncio
import os
from pathlib import Path
import tempfile
from typing import Final

DEFAULT_FILE_MODE: Final[int] = 0o600
DIRECTORY_MODE: Final[int] = 0o700


class FileSystem:
    """Асинхронный доступ к файлам внутри корневого каталога.

    В CPython нет асинхронного API файловой системы, поэтому блокирующие вызовы уходят в
    пул потоков, и цикл событий не ждёт диск. Объект не знает о домене: он читает и
    пишет байты, а смысл файлов определяет репозиторий.
    """

    def __init__(self, root: Path) -> None:
        """Инициализация класса.

        Args:
            root (Path): Корневой каталог, внутри которого доступны файлы.
        """
        self._root = root.resolve()

    async def read(self, name: str) -> bytes:
        """Читает файл.

        Args:
            name (str): Имя файла относительно корневого каталога.

        Returns:
            bytes: Содержимое файла.
        """
        path = self._resolve(name)

        return await asyncio.to_thread(path.read_bytes)

    async def write(self, name: str, payload: bytes, *, mode: int = DEFAULT_FILE_MODE) -> None:
        """Атомарно записывает файл.

        Args:
            name (str): Имя файла относительно корневого каталога.
            payload (bytes): Содержимое файла.
            mode (int, optional): Права доступа к файлу. Defaults to `0o600`.
        """
        path = self._resolve(name)

        await asyncio.to_thread(self._write_atomically, path, payload, mode)

    @staticmethod
    def _write_atomically(path: Path, payload: bytes, mode: int) -> None:
        """Пишет содержимое во временный файл и подменяет им целевой.

        Временный файл создаётся в каталоге цели, поэтому подмена остаётся атомарной
        и на разных файловых системах. `fsync` гарантирует, что данные на диске
        появятся раньше, чем имя файла станет указывать на них.

        Args:
            path (Path): Целевой файл.
            payload (bytes): Содержимое файла.
            mode (int): Права доступа к файлу.
        """
        path.parent.mkdir(parents=True, exist_ok=True, mode=DIRECTORY_MODE)

        descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
        temporary_path = Path(temporary_name)

        try:
            with os.fdopen(descriptor, "wb") as file:
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())

            os.chmod(temporary_path, mode)
            os.replace(temporary_path, path)

        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise

    def _resolve(self, name: str) -> Path:
        """Приводит имя файла к пути и проверяет, что путь остаётся в корне.

        Символические ссылки раскрываются до проверки, поэтому ссылка за пределы
        корневого каталога тоже отклоняется.

        Args:
            name (str): Имя файла относительно корневого каталога.

        Raises:
            ValueError: Если путь выходит за корневой каталог.

        Returns:
            Path: Путь к файлу внутри корневого каталога.
        """
        path = (self._root / name).resolve()

        if not path.is_relative_to(self._root):
            msg = "File path escapes the root directory."
            raise ValueError(msg) from None

        return path
