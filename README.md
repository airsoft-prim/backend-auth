# backend-auth

Сервер аутентификации страйкбольного портала Airsoft Prim.

## Разработка

Нужны Python 3.14, [uv](https://docs.astral.sh/uv/) и Docker для PostgreSQL и Redis.

```bash
uv sync
uv run pre-commit install --install-hooks
docker compose --profile dev up -d postgres redis
uv run python main.py
```

Хуки запускайте через `uv run pre-commit run --all-files` от обычного пользователя.
Не запускайте `uv` и `pre-commit` с повышенными правами: кэш `%LOCALAPPDATA%\uv` и
`.venv` должны принадлежать вашему пользователю, иначе следующие запуски без
администратора завершатся с `Access denied`.

Git хранит исходники с LF (`.gitattributes`, `.editorconfig`), поэтому на Windows
не нужно менять `core.autocrlf`. Локальные ключи подписи пишутся в `.keys/`; в
контейнере путь задаётся Dockerfile.
