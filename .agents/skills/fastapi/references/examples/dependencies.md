# Example: dependencies

## Using a dependency

```python
from typing import Annotated

from fastapi import APIRouter, Depends

from myapp.services import OrderService

from .docs import GET_ORDER_DOCS
from .schemas import Order

router = APIRouter(prefix="/orders", tags=["Orders"])


async def get_order_service() -> OrderService:
    """Provides the order service for the duration of the request.

    Returns:
        OrderService: Service that owns the order flow.
    """
    return OrderService()


@router.get("/{order_id}", **GET_ORDER_DOCS)
async def get_order(
    order_id: int,
    service: Annotated[OrderService, Depends(get_order_service)],
) -> Order:
    """Returns an order by its identifier.

    Args:
        order_id (int): Identifier of the order.
        service (OrderService): Service that owns the order flow.

    Returns:
        Order: Order found by the identifier.
    """
    return await service.acquire(order_id)
```

## A dependency built from another dependency

```python
async def get_order_service(
    repository: Annotated[OrderRepository, Depends(get_order_repository)],
) -> OrderService:
    """Provides the order service for the duration of the request.

    Args:
        repository (OrderRepository): Repository the service reads and writes through.

    Returns:
        OrderService: Service bound to the given repository.
    """

    return OrderService(order_repository=repository)
```

No `yield` here: nothing stays open after the function returns, and FastAPI resolves the nested
dependency for you. Repeated uses normally share the request-cached result; use_cache=False opts out.

## A dependency that owns a connection

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Provides a database session for the duration of the request.

    Yields:
        AsyncSession: Session owned by the dependency context.
    """
    async with async_session() as session:
        yield session
```

Acquire before `yield` and release through a context manager or `try/finally`.
Cleanup timing depends on dependency scope; it is not always the same point in
response delivery.

## A dependency whose target must be named

```python
from collections.abc import AsyncGenerator, Callable

from myapp.enums import Shard


def get_client(shard: Shard) -> Callable[[], AsyncGenerator[Client]]:
    """Builds the client dependency bound to the given shard.

    Args:
        shard (Shard): Logical store the client must talk to.

    Returns:
        Callable[[], AsyncGenerator[Client]]: Dependency callable for `Depends`.
    """

    async def _get_client() -> AsyncGenerator[Client]:
        """Yields a client of that shard for the duration of the request."""
        async with client_factory(shard) as connected:
            yield connected

    return _get_client


async def get_report_service(
    client: Annotated[Client, Depends(get_client(Shard.REPORTS))],
) -> ReportService:
    """Provides the report service for the duration of the request."""
    return ReportService(client=client)
```

`Depends` accepts any callable, so a factory can return the dependency and the endpoint can name
its target: a named enum member stands where a magic number or a connection string would otherwise
sit. `Client` and `client_factory` stand for the project's own storage client.

## Substituting a dependency in a test

```python
from collections.abc import Iterator

from fastapi import FastAPI
import pytest

from tests.asgi_client import ASGIClient


@pytest.fixture
def api_client(application: FastAPI) -> Iterator[ASGIClient]:
    """Provide a client with an isolated service override.

    Args:
        application (FastAPI): Application under test.

    Yields:
        ASGIClient: Client using the test repository.
    """
    previous_overrides = application.dependency_overrides.copy()
    application.dependency_overrides[get_order_service] = lambda: OrderService(
        order_repository=in_memory_repository,
    )
    try:
        yield ASGIClient(application)
    finally:
        application.dependency_overrides.clear()
        application.dependency_overrides.update(previous_overrides)
```

The application and repository come from fixtures. Reuse the existing client;
manage its lifecycle if it owns resources. For dependencies returned by factories,
retain the exact callable used in `Depends` when tests need to override it:

```python
reports_client_dependency = get_client(Shard.REPORTS)
```

Override that callable, not a new factory result: a fresh closure has a different
identity. Keep providers importable and let FastAPI resolve them. Reuse cached
settings; do not use `app.state` to register request-scoped objects.
