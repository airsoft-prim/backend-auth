# Example: status codes, errors and probes

## Choosing a code

- 201 — the request created something; the response carries the created resource.
- 200 — the request returned something, including a freshly issued token-like payload.
- 204 — the command succeeded and has nothing to return; a healthy probe answers 204 as well.
- 422 — the request body did not validate. FastAPI produces it; do not build it by hand.
- 405 — the method is not allowed on this path. Produced by routing, with the `allow` header.
- 503 — a probe found a dependency it cannot serve traffic without.

Two stages of one operation may share a URL and differ by method: `POST` starts the stage, `PATCH`
confirms it, and each gets its own documentation constant.

## Raising at the boundary

```python
from fastapi import HTTPException, status


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

    Raises:
        HTTPException: No order with the given identifier exists.
    """
    order = await service.acquire(order_id)

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No order with this identifier exists.",
        )

    return order
```

## Or one handler for many endpoints

```python
from fastapi import Request, status
from fastapi.responses import JSONResponse


@application.exception_handler(OrderNotFoundError)
async def order_not_found_handler(_: Request, error: OrderNotFoundError) -> JSONResponse:
    """Translates a missing order into a response.

    Args:
        error (OrderNotFoundError): Error raised below the HTTP layer.

    Returns:
        JSONResponse: Response with the status the contract promises.
    """
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(error)},
    )
```

## A probe that must always answer

```python
from fastapi.responses import PlainTextResponse


@router.get("/readiness", **READINESS_DOCS)
async def readiness_healthcheck() -> PlainTextResponse:
    """Checks that the application is ready to serve traffic.

    Returns:
        PlainTextResponse: Empty response carrying the readiness status.
    """
    try:
        async with connect() as client:
            await client.ping()

    except ClientError, Exception:  # noqa: BLE001
        logger.critical("Cache is unavailable.")
        return PlainTextResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    logger.success("Application ready.")
    return PlainTextResponse(status_code=status.HTTP_204_NO_CONTENT)
```

## Notice

- The success code is declared in the documentation constant and the handler returns the payload;
  FastAPI puts both into the OpenAPI document.
- `HTTPException` belongs to the HTTP boundary. Code that knows nothing about HTTP — a collaborator
  or a client wrapper — raises its own error types, and one `exception_handler` maps them when many
  endpoints share the mapping.
- A handler that returns a custom body keeps the status visible in the code; a bare 500 from an
  unhandled exception is not an error contract.
- Every failure the client can receive is declared under `responses` in the documentation constant,
  or Swagger promises less than the endpoint does.
- A probe answers with a bare status and no body: the reason is not leaked to the caller, it lives
  in the log where the operator sees which component failed.
- The broad catch is the exception, never the norm, and is always marked for the linter — under ruff
  `# noqa: BLE001`, under another project its own suppression syntax.
- `except ClientError, Exception:` is Python 3.14 syntax (PEP 758) and means
  `except (ClientError, Exception):`. On older interpreters only the parenthesized form parses.
- Exception messages are English and built into a variable before raising:
  `msg = "Order not found."; raise ValueError(msg)`. `print` is never used; logs go through the
  project's logger at a severity that matches the event.
