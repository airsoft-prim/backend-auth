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
    """Application lifespan."""
    logger.info("Application starting up...")

    worker = build_worker()
    worker.start()
    logger.success("Background worker started.")

    logger.success("Application started.")

    yield

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

# Production: the imported object itself.
uvicorn.run(application, host="localhost", port=8000)
```

## Notice

- `lifespan(_: FastAPI)`: the application argument is unnamed unless the lifespan genuinely reads
  it, and the yield type is `None`. The annotation stays generic because the body yields nothing.
- The lifespan replaces the deprecated `@app.on_event("startup")` / `("shutdown")` pair: one place
  shows everything that happens around the application's life.
- Startup starts long-running background work; the code after `yield` stops exactly that work and
  nothing else. A `try/finally` around the `yield` is the form to use when teardown must survive
  cancellation or a failed startup.
- Pools, engines and clients that live for the process are created once, when their module is
  imported — not on every request and not inside the lifespan's startup body, where they would be
  invisible to anything that imports the app.
- The lifespan runs once per process. With several uvicorn workers, every worker runs its own copy,
  so a "single global" started here is really one per worker.
- Phase boundaries are logged and named: `info` when a phase starts, `success` when a step finished,
  `warning` before shutdown. Messages are English.
- The application object stays `title`, `description`, `version`, `lifespan` and its routers.
  FastAPI's own defaults stay in place: `/docs`, `/redoc` and `/openapi.json` are served, no
  `tags_metadata`, no custom docs URLs, no middleware stack and no exception handlers unless
  something needs them.
- Only the reload case needs an import string: `reload=True` re-imports the module, and an
  already-constructed app object cannot be re-imported.
