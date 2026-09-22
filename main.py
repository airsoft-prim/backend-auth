import uvicorn

from src import application
from src.core.configs import config


def main() -> None:
    """Точка входа в приложение."""
    if not config.app.DEBUG:
        uvicorn.run(application, host="localhost", port=8000)

    else:
        uvicorn.run("main:application", host="localhost", port=8000, reload=True)


if __name__ == "__main__":
    main()
