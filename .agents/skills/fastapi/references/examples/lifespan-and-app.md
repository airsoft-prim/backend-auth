# Example: lifespan and the application object

## The application object

```python
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Final

from fastapi import FastAPI
from loguru import logger

from myapp.api import main_router

APP_DESCRIPTION: Final[str] = """
Order processing service.
"""


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    """Start and stop the background worker.

    Args:
        _ (FastAPI): Application supplied by the framework; unused.

    Yields:
        None: Control while the application serves requests.
    """
    logger.info("Application starting up...")

    worker = build_worker()
    worker.start()
    logger.success("Background worker started.")

    logger.success("Application started.")

    try:
        yield
    finally:
        logger.warning("Application is shutting down.")
        await worker.stop()


application = FastAPI(
    title="Order Service",
    description=APP_DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
)

application.include_router(main_router)
```

## Serving it

```python
import uvicorn

from myapp import application

# Development: an import string, which is what makes reload possible.
uvicorn.run("myapp:application", host="localhost", port=8000, reload=True)

# Single-process production without reload: an app object is also supported.
uvicorn.run(application, host="localhost", port=8000)
```

## Ownership and configuration

The lifespan runs per worker. Stop work it owns and protect teardown with
`try/finally` when exceptions can cross `yield`. Resources acquired during startup
need cleanup protection if a later startup step fails.

Reuse project resource factories and the composition root. This example does not
require import-time network connections or moving every pool into the same place.
Preserve existing docs URL configuration, middleware, and exception handlers.

Use import strings for reload and multi-worker launches. The app-object form
above is an alternative for single-process serving without reload.
