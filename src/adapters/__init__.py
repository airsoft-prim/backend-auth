"""Driven-адаптеры: реализуют порты из `domain/ports.py`.

Здесь адаптеры к внешним системам и библиотекам: БД, кеш, файловая система,
хеширование паролей. Driving-адаптеры (HTTP, cron) лежат отдельно — в `interface/`
и `scheduler/`.
"""

from ._base import Repository

__all__ = ["Repository"]
