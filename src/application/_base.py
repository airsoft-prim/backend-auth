from abc import ABC, abstractmethod
from typing import Any


class AbstractUseCase(ABC):
    """Базовый класс use case.

    Фиксирует единую точку входа — асинхронный `__call__`. Сигнатура намеренно
    свободная (`*args`, `**kwargs`), чтобы не препятствовать специфичным параметрам
    каждого сценария; конкретный use case сужает её до собственных аргументов.
    """

    @abstractmethod
    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Выполняет сценарий использования."""
        message = "Use Case has no effect."
        raise NotImplementedError(message) from None
