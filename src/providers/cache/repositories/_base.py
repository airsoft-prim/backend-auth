from collections.abc import Mapping
import re
from string import Template
from typing import Any, Literal

from redis.asyncio import Redis

type KeyStub = Literal["*"]


class RedisRepository:
    """Репозиторий для взаимодействия с данными в Redis."""

    _key_template: Template

    @property
    def key_template(self) -> Template:
        """Шаблон ключа Redis для репозитория."""
        return self._key_template

    def __init__(self, client: Redis) -> None:
        """Инициализация класса.

        Args:
            client (Redis): Асинхронный клиент Redis.
        """
        self.client = client

    def compile_template(self, values: Mapping[str, Any | KeyStub]) -> str:
        """Собирает ключ Redis из его шаблона, указанного в репозитории.

        Если значений не хватает для полноценной компиляции шаблона, то
        оставшиеся параметры заполняются KeyStub. KeyStub также может быть
        передан в качестве значения для шаблонного параметра.

        Args:
            values (Mapping[str, Any | KeyStub]): Значения для заполнения.

        Returns:
            str: Заполненный шаблон, готовый ключ Redis.
        """
        # Первый проход подставляет известные значения, остальные оставляет текстом.
        filled = Template(self._key_template.safe_substitute(**values))

        def _replacer(match: re.Match[str]) -> str:
            # Группы "named" и "braced" взаимоисключающие: $name и ${name}.
            name = match.group("named") or match.group("braced")
            if name:
                # Значения не было — подставляем "*", glob-маску Redis.
                return "*"
            # Остальное — "$$" или "$" без имени: отдаём совпадение как есть.
            return match.group(0)

        return re.sub(filled.pattern, _replacer, filled.template)
