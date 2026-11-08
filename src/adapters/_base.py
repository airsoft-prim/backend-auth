from collections.abc import Generator
from contextlib import contextmanager

from src.domain.errors import RepositoryError


class Repository:
    """Базовый класс репозитория.

    Предоставляет контекст преобразования исключений внешних ресурсов в `RepositoryError` с
    сохранением причины ошибки.
    """

    @contextmanager
    def _as_repository_error(self, message: str) -> Generator[None]:
        """Преобразует исключение операции репозитория в `RepositoryError`.

        Args:
            message (str): Сообщение для `RepositoryError`.

        Yields:
            None: Управление блоку файловой, `Redis`- или SQL-операции.

        Raises:
            RepositoryError: Блок контекста выбросил исключение класса `Exception`.
        """
        try:
            yield  # Возвращает контроль интерпретатору

        except Exception as error:
            raise RepositoryError(message) from error
