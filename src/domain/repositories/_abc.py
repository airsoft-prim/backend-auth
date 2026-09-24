from abc import ABC


class AbstractRepository(ABC):  # noqa: B024
    """Абстрактный класс репозитория.

    Конкретные реализации репозиториев должны служить прослойкой
    между архитектурой (База данных, Кеш) и биз-нес логикой. Именно
    репозитории должны знать, как и откуда брать данные.
    """

    def __repr__(self) -> str:
        class_name = self.__class__.__name__

        return f"{class_name}<{id(self)=}>"
