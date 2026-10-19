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
dependency for you. A dependency used twice inside one request is resolved once and its result
reused.

## A dependency that owns a connection

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Provides a database session for the duration of the request.

    Yields:
        AsyncGenerator[AsyncSession]: Session closed when the request is done.
    """
    async with async_session() as session:
        yield session
```

Everything after the `yield` is cleanup: it runs when the response is on its way out, including
when the handler raised. Code before the `yield` runs before the handler does.

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
import pytest
from fastapi import FastAPI

from tests.asgi_client import ASGIClient

application.dependency_overrides[get_order_service] = lambda: OrderService(
    order_repository=in_memory_repository
)


@pytest.fixture
def api_client(application: FastAPI) -> Iterator[ASGIClient]:
    """Provides a client over the application and clears overrides afterwards.

    Yields:
        Iterator[ASGIClient]: Client bound to the application under test.
    """
    yield ASGIClient(application)
    application.dependency_overrides.clear()
```

## Notice

- Dependencies are declared with `Annotated[T, Depends(...)]` and never called by hand inside a
  handler: calling them would open a second connection and skip the override.
- A dependency returns one object. Tuples and dicts of several values turn the signature into a
  puzzle; split them into two dependencies instead.
- Dependency callables stay module-level and importable. `dependency_overrides` matches them by
  identity, so a factory closure created inside a route module cannot be substituted.
- Overrides are cleared in teardown: a leaked override silently changes every test that runs after.
- `app.state` is not a dependency registry for request-scoped objects: a dependency either builds a
  cheap object or yields a scoped resource, and the request end closes it.
- A settings object is not injected per route: one cached instance is shared, so no request pays for
  re-reading configuration.
- Only the dependency function knows the concrete client type; the endpoint sees the type it
  declares, which is what makes it swappable in tests.
