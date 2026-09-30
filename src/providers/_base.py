from collections.abc import Generator
from contextlib import contextmanager

from src.general.exceptions import RepositoryError


class Repository:
    """Базовый класс репозитория."""

    @contextmanager
    def _as_repository_error(self, message: str) -> Generator[None]:
        """Контекстный менеджер, позволяющий удобно перехватить все ошибки,
        возникающие в процессе работы репозитория и транслировать их в
        RepositoryError.

        Args:
            message (str): Сообщение к ошибке.

        Raises:
            RepositoryError: Ошибка работы репозитория.
        """
        try:
            yield  # Возвращает контроль интерпретатору

        except Exception as error:
            raise RepositoryError(message) from error
