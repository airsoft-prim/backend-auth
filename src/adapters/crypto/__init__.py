"""Адаптер хеширования паролей.

Экспортирует `PASSWORD_HASHER`, использующий Argon2 через pwdlib.

Предоставляет реализацию `PasswordHasher` при сборке сценариев регистрации и входа.
"""

from .hasher import PASSWORD_HASHER

__all__ = ["PASSWORD_HASHER"]
