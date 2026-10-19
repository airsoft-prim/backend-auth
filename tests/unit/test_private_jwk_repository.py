"""Тесты репозитория приватного ключа подписи."""

from pathlib import Path

import pytest

from src.general.exceptions import RepositoryError
from src.providers.filesystem import FileSystem
from src.providers.filesystem.repositories import PrivateJWKRepository

PAYLOAD = b"first key payload"
ROTATED_PAYLOAD = b"rotated key payload"


async def test_acquire_returns_none_before_first_store(
    private_jwk_repository: PrivateJWKRepository,
) -> None:
    """Приватный ключ ещё не сгенерирован.

    Given: keyfile отсутствует,
    When: репозиторий отдаёт приватный ключ,
    Then: он возвращает None — сервис по этому признаку генерирует новый ключ.
    """
    assert await private_jwk_repository.acquire() is None


async def test_store_writes_key_file(
    private_jwk_repository: PrivateJWKRepository,
    key_store_dir: Path,
) -> None:
    """Запись приватного ключа.

    Given: keyfile ещё не существует,
    When: репозиторий записывает приватный ключ,
    Then: файл создан, а последующее чтение возвращает его содержимое.
    """
    await private_jwk_repository.store(PAYLOAD)

    assert (key_store_dir / PrivateJWKRepository.FILE_NAME).read_bytes() == PAYLOAD
    assert await private_jwk_repository.acquire() == PAYLOAD


async def test_acquire_reads_latest_key_after_rotation(
    private_jwk_repository: PrivateJWKRepository,
) -> None:
    """Ротация приватного ключа.

    Given: репозиторий уже отдал сгенерированный приватный ключ,
    When: ключ записывается заново, как при ротации,
    Then: следующее чтение возвращает ротированный ключ, а не прежний.
    """
    await private_jwk_repository.store(PAYLOAD)
    assert await private_jwk_repository.acquire() == PAYLOAD

    await private_jwk_repository.store(ROTATED_PAYLOAD)

    assert await private_jwk_repository.acquire() == ROTATED_PAYLOAD


async def test_repository_does_not_keep_state_between_instances(
    private_jwk_repository: PrivateJWKRepository,
    key_store_dir: Path,
) -> None:
    """Отсутствие состояния у репозитория.

    Given: один экземпляр репозитория записал приватный ключ,
    When: другой экземпляр, из другого запроса, читает ключ,
    Then: он видит файл с диска, а не состояние первого экземпляра.
    """
    await private_jwk_repository.store(PAYLOAD)

    repository = PrivateJWKRepository(FileSystem(key_store_dir))

    assert await repository.acquire() == PAYLOAD


async def test_acquire_reports_unreadable_file_as_repository_error(
    private_jwk_repository: PrivateJWKRepository,
    key_store_dir: Path,
) -> None:
    """Ошибка чтения keyfile.

    Given: по пути keyfile лежит каталог, а не файл,
    When: репозиторий читает приватный ключ,
    Then: ошибка файловой системы приходит как ошибка репозитория.
    """
    (key_store_dir / PrivateJWKRepository.FILE_NAME).mkdir(parents=True)

    with pytest.raises(RepositoryError, match="reading error"):
        await private_jwk_repository.acquire()
