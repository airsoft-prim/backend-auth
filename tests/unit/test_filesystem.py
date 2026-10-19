"""Тесты объекта файловой системы."""

import os
from pathlib import Path
import stat

import pytest

from src.providers.filesystem import FileSystem

FILE_NAME = "key.pem"
PAYLOAD = b"first key payload"
ROTATED_PAYLOAD = b"rotated key payload"
OWNER_ONLY_MODE = 0o600


def _file_names(directory: Path) -> list[str]:
    """Перечисляет имена файлов каталога по алфавиту.

    Args:
        directory (Path): Каталог файловой системы.

    Returns:
        list[str]: Имена файлов в каталоге.
    """
    return sorted(path.name for path in directory.iterdir())


async def test_read_fails_when_file_is_missing(file_system: FileSystem) -> None:
    """Отсутствующий файл.

    Given: в каталоге нет запрошенного файла,
    When: объект файловой системы читает файл,
    Then: ошибка отсутствия файла не скрывается — её обрабатывает репозиторий.
    """
    with pytest.raises(FileNotFoundError):
        await file_system.read(FILE_NAME)


async def test_write_creates_directory_and_file(
    file_system: FileSystem,
    key_store_dir: Path,
) -> None:
    """Первая запись в пустой каталог.

    Given: корневого каталога ещё нет,
    When: объект файловой системы записывает файл,
    Then: каталог и файл созданы, а содержимое читается обратно.
    """
    await file_system.write(FILE_NAME, PAYLOAD)

    assert (key_store_dir / FILE_NAME).read_bytes() == PAYLOAD
    assert await file_system.read(FILE_NAME) == PAYLOAD


async def test_write_replaces_file_without_temporary_leftovers(
    file_system: FileSystem,
    key_store_dir: Path,
) -> None:
    """Перезапись файла.

    Given: файл уже записан,
    When: объект файловой системы записывает новое содержимое,
    Then: читается новое содержимое, а временные файлы не остаются в каталоге.
    """
    await file_system.write(FILE_NAME, PAYLOAD)
    await file_system.write(FILE_NAME, ROTATED_PAYLOAD)

    assert await file_system.read(FILE_NAME) == ROTATED_PAYLOAD
    assert _file_names(key_store_dir) == [FILE_NAME]


@pytest.mark.skipif(os.name != "posix", reason="File modes are POSIX-specific.")
async def test_write_restricts_file_permissions(
    file_system: FileSystem,
    key_store_dir: Path,
) -> None:
    """Права доступа к записанному файлу.

    Given: файл записан,
    When: проверяются его права доступа,
    Then: файл доступен только владельцу.
    """
    await file_system.write(FILE_NAME, PAYLOAD)

    mode = stat.S_IMODE((key_store_dir / FILE_NAME).stat().st_mode)

    assert mode == OWNER_ONLY_MODE


async def test_read_rejects_path_outside_root(file_system: FileSystem) -> None:
    """Путь за пределы корневого каталога на чтении.

    Given: имя файла пытается выйти из корневого каталога,
    When: объект файловой системы читает файл,
    Then: обращение отклоняется до работы с диском.
    """
    with pytest.raises(ValueError, match="escapes the root directory"):
        await file_system.read("../escaped.pem")


async def test_write_rejects_path_outside_root(file_system: FileSystem) -> None:
    """Путь за пределы корневого каталога на записи.

    Given: имя файла пытается выйти из корневого каталога,
    When: объект файловой системы пишет файл,
    Then: запись отклоняется до работы с диском.
    """
    with pytest.raises(ValueError, match="escapes the root directory"):
        await file_system.write("../escaped.pem", PAYLOAD)
