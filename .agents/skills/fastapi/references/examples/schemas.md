# Example: schemas

## A policy as an annotated alias

In the schemas module:

```python
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, SecretStr


class OrderStatus(StrEnum):
    """Status of an order."""

    DRAFT = "draft"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


def check_amount(value: Decimal) -> Decimal:
    """Checks that an amount is positive and has at most two decimals.

    Args:
        value (Decimal): Amount taken from the request body.

    Returns:
        Decimal: The amount unchanged, if the check passed.

    Raises:
        ValueError: The amount does not meet the policy.
    """
    if value <= 0 or value.as_tuple().exponent < -2:
        msg = "Amount must be positive and have at most two decimals."
        raise ValueError(msg)

    return value


Amount = Annotated[Decimal, AfterValidator(check_amount)]
```

Another feature that needs the same policy imports `Amount`. It does not re-declare the check and
does not copy the message.

## Request and response bodies

```python
class OrderLineRequestBody(BaseModel):
    """A single line of an order."""

    item_id: int = Field(description="Identifier of the item.", examples=[17])
    quantity: int = Field(gt=0, description="Number of items to reserve.", examples=[2])


class CreateOrderRequestBody(BaseModel):
    """Request body of an order creation."""

    customer_id: int = Field(description="Identifier of the customer.", examples=[42])
    note: str | None = Field(default=None, description="Free-form note for the order.")
    card_token: SecretStr = Field(description="Single-use payment token.")
    lines: list[OrderLineRequestBody] = Field(description="Lines to reserve.")


class Order(BaseModel):
    """Stored order returned to its owner."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Identifier of the order.", examples=[1024])
    status: OrderStatus = Field(description="Current status of the order.")
    total: Amount = Field(description="Total amount of the order.")
    created_at: datetime = Field(description="Moment the order was created.")
```

## A polymorphic payload

```python
class CardPayment(BaseModel):
    """Payment with a stored card."""

    kind: Literal["card"]
    token: SecretStr


class TransferPayment(BaseModel):
    """Payment by transfer."""

    kind: Literal["transfer"]
    account: str


type PaymentMethod = Annotated[CardPayment | TransferPayment, Field(discriminator="kind")]
```

## Notice

- Every field carries a description; `examples` appear where the value is not self-evident, so
  Swagger shows something better than `string`.
- Constraints live on the field (`gt=0`) and policies live in validators; both are visible in the
  generated schema.
- Secrets are `SecretStr`, closed vocabularies are shared enums, and timestamps are timezone-aware
  (they parse into `datetime`).
- Bodies are named `<Action>RequestBody`; responses are named for what they mean (`Order`,
  `OrderList`), never for their direction (`OrderResponse`) or their JSON shape.
- Models built from ORM objects set `ConfigDict(from_attributes=True)`; models that only travel over
  HTTP never do.
- A `@field_validator` is paired with `@classmethod`, typed `cls, value -> value` and documented the
  same way as a function.
- Validators raise `ValueError` with an English message built into a variable first
  (`msg = "..."; raise ValueError(msg)`); the framework turns it into a 422 for the caller.
- Polymorphic payloads use a discriminated union, so the OpenAPI document shows the alternatives
  instead of a shapeless object.
