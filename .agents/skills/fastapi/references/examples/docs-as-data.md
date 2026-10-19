# Example: OpenAPI documentation as data

## The shared shape

Declared once and reused by every route module:

```python
from enum import Enum
from typing import Any, TypedDict


class RouteDocs(TypedDict, total=False):
    """Shape of the documentation data attached to a path operation."""

    summary: str
    operation_id: str
    description: str
    deprecated: bool
    tags: list[str | Enum]
    status_code: int
    response_description: str
    responses: dict[int | str, dict[str, Any]] | None
```

## One constant per path operation

```python
from fastapi import status

from myapp.docs_types import RouteDocs

CREATE_ORDER_DOCS: RouteDocs = {
    "summary": "Creates an order.",
    "description": (
        "Reserves stock for every line and stores the order as a draft. Payment is not "
        "taken here: reservations expire after 15 minutes. Idempotency keys are not "
        "supported yet."
    ),
    "status_code": status.HTTP_201_CREATED,
    "deprecated": False,
}

GET_ORDER_DOCS: RouteDocs = {
    "summary": "Returns an order.",
    "description": "Returns the order with its lines and its current status.",
    "status_code": status.HTTP_200_OK,
    "deprecated": False,
    "responses": {
        status.HTTP_404_NOT_FOUND: {"description": "No order with this identifier exists."},
    },
}

CANCEL_ORDER_DOCS: RouteDocs = {
    "summary": "Cancels an order.",
    "description": "Moves the order to the cancelled status and releases the reservations.",
    "status_code": status.HTTP_204_NO_CONTENT,
    "deprecated": False,
}
```

## Reaching the decorator

```python
@router.post("", **CREATE_ORDER_DOCS)
async def create_order(...) -> Order: ...


@router.get("/{order_id}", **GET_ORDER_DOCS)
async def get_order(...) -> Order: ...
```

## Notice

- `RouteDocs` mirrors the path operation's keyword arguments, so the constant and the decorator
  cannot disagree. It deliberately has no `response_model`: the model comes from the return
  annotation, and a second declaration of the same contract would drift.
- `total=False` keeps optional keys optional: `operation_id`, `response_description` and `responses`
  appear only where they add something.
- Codes are `fastapi.status` constants, so a reader never has to remember what 201 means.
- `deprecated` is written out every time; an absent key should never read as "not decided".
- Text is written for whoever opens Swagger: a one-sentence `summary` with a period, and a
  `description` that states behavior, side effects and what is not implemented yet.
- Names repeat the operation's intent (`CANCEL_ORDER_DOCS` for `cancel_order`), so the documentation
  module reads in the same order as the route module.
- The dict is never written inline in the decorator and never repeats a schema: it is documentation,
  not a contract.
- Human-facing text follows the language rule: the team's language, one language per module.
