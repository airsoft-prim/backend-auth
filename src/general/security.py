"""Общие средства безопасности сервиса."""

from typing import Final

from pwdlib import PasswordHash

# Хешер паролей один на процесс. Argon2id с параметрами по умолчанию.
PASSWORD_HASHER: Final[PasswordHash] = PasswordHash.recommended()
