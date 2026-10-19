# Example: routers

## One router per prefix

```python
from fastapi import APIRouter

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("", **CREATE_ORDER_DOCS)
async def create_order(...) -> Order: ...


@router.get("/{order_id}", **GET_ORDER_DOCS)
async def get_order(...) -> Order: ...


@router.delete("/{order_id}", **CANCEL_ORDER_DOCS)
async def cancel_order(...) -> None: ...
```

The decorators carry method, path and docs only: no `tags`, no `summary`, no `status_code`, no
`response_model`.

## Gathering routers

```python
from fastapi import APIRouter

from .health import router as health_router
from .orders import router as orders_router

main_router = APIRouter()

main_router.include_router(health_router)
main_router.include_router(orders_router)

__all__ = ["main_router"]
```

## Attaching to the application

```python
application = FastAPI(title="Order Service", lifespan=lifespan)

application.include_router(main_router)
```

## A versioned API

```python
router = APIRouter(prefix="/v2/orders", tags=["Orders"])
```

`include_router(router, prefix="/v2")` stacks a second prefix onto the same router and is the
alternative when a whole group moves together.

## Notice

- The prefix exists once, on the router. Endpoint paths start with `/` and hold the rest of the URL:
  `""` is the collection under the prefix, `"/{order_id}"` a member.
- No path ends with a slash. `/orders/` and `/orders` are different routes to FastAPI; one of them
  triggers the redirect that some clients do not follow.
- One tag per router is what groups the endpoints in Swagger. A list of internal labels there makes
  the documentation harder to read, not more precise.
- Router-level `dependencies=` and `responses=` exist in FastAPI; this style keeps them per endpoint
  so that reading one decorator tells the whole story.
- Routers are gathered in one place and attached once. `include_router` is the only way a router
  reaches the application, and this module is the exposure list.
- A feature that needs a guard adds it to the endpoints that need it rather than to the router, so
  an endpoint without the guard stays visibly without it.
