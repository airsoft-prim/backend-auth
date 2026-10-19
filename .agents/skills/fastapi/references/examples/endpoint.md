# Example: path operations

## A command that creates a resource

In the module that declares the router:

```python
from typing import Annotated

from fastapi import APIRouter, Depends

from myapp.services import OrderService

from .docs import CREATE_ORDER_DOCS
from .schemas import CreateOrderRequestBody, Order

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("", **CREATE_ORDER_DOCS)
async def create_order(
    body: CreateOrderRequestBody,
    service: Annotated[OrderService, Depends(get_order_service)],
) -> Order:
    """Creates an order.

    Args:
        body (CreateOrderRequestBody): Order to create.
        service (OrderService): Service that owns the order flow.

    Returns:
        Order: Stored order with its assigned identifier.
    """
    return await service.create(body)
```

## A read with a constrained path parameter

```python
@router.get("/{order_id}", **GET_ORDER_DOCS)
async def get_order(
    order_id: Annotated[int, Path(ge=1)],
    service: Annotated[OrderService, Depends(get_order_service)],
    expand: Annotated[bool, Query(description="Include the order lines.")] = False,
) -> Order:
    """Returns an order by its identifier.

    Args:
        order_id (int): Identifier of the order.
        service (OrderService): Service that owns the order flow.
        expand (bool): Whether to include the order lines.

    Returns:
        Order: Order found by the identifier.
    """
    return await service.acquire(order_id, expand=expand)
```

## A command with an empty body

```python
@router.delete("/{order_id}", **CANCEL_ORDER_DOCS)
async def cancel_order(
    order_id: Annotated[int, Path(ge=1)],
    service: Annotated[OrderService, Depends(get_order_service)],
) -> None:
    """Cancels an order.

    Args:
        order_id (int): Identifier of the order to cancel.
        service (OrderService): Service that owns the order flow.
    """
    await service.cancel(order_id)
```

## A contract stub

An endpoint whose interface is final and whose behavior is not written yet:

```python
from typing import Any


@router.post("/{order_id}/refunds", **REFUND_ORDER_DOCS)
async def refund_order(order_id: int, current_user: Any) -> None:
    """Refunds an order.

    Args:
        order_id (int): Identifier of the order to refund.
        current_user (Any): Owner of the token the request came with.
    """
    raise NotImplementedError
```

## Notice

- The decorator is the contract you read first: method, path, spread docs. Nothing else is on it.
- `response_model=` never appears. The return annotation is the model, FastAPI feeds it into the
  OpenAPI document, and a `dict` return would silently drop it.
- An endpoint with nothing to return is annotated `-> None` and takes its 204 from the docs
  constant; a non-JSON body is an explicit `PlainTextResponse` built in the handler.
- Parameters are `Annotated`, markers included: `Annotated[int, Path(ge=1)]` both documents the
  constraint and enforces it, so the handler receives a value that is already valid.
- `Annotated[T, Depends(...)]` has no default value: the dependency is named once, in the signature,
  and never called by hand inside the body.
- A default value is for data, not for dependencies: `expand: bool = False` is a request value,
  `x: T = Depends(...)` is not this style.
- Return types stay narrow. `Any`, `dict` and bare `list` hide the response shape from clients and
  from the OpenAPI document.
- The stub is a real contract from day one: whoever writes the behavior edits only the body.

## Related

- Documentation constants used by the decorators: `docs-as-data.md`.
- Where `get_order_service` comes from: `dependencies.md`.
