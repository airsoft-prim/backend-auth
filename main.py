from typing import Final

import uvicorn

from src import application
from src.core.configs import config

# Привязка к localhost делает проброс портов наружу невозможным.
HOST: Final[str] = "0.0.0.0"  # noqa: S104 # nosec: B104
PORT: Final[int] = 8000


def main() -> None:
    """Точка входа в приложение."""
    if not config.app.DEBUG:
        uvicorn.run(application, host=HOST, port=PORT, access_log=False)

    else:
        uvicorn.run("main:application", host=HOST, port=PORT, reload=True)


if __name__ == "__main__":
    main()
