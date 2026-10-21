---
name: pytest
description: >
  Guidelines for writing pytest tests in Python projects following Given/When/Then/Clean
  patterns, with business-readable docstrings and organized test layers (unit, functional,
  interface, integration). Use this skill whenever the user asks to write tests, add
  test coverage, create a test suite, set up pytest, write unit tests, write integration tests,
  write functional tests, or validate Python code with tests. Also trigger
  when the user mentions "test coverage", "TDD", "test-driven", "pytest", "mocking",
  "happy path tests", "fail branch tests", or when they ask how to structure a
  tests/ folder.
---

# Pytest Testing Guidelines

## Core Philosophy

Tests serve two purposes: **verifying correctness** and **documenting behavior**. Every test
should read like a specification of what the system does, written in business language.

---

## Test Structure: Given / When / Then / Clean

All tests follow this four-phase pattern:

```python
def test_<behavior_description>():
    # Given – set up preconditions and inputs
    ...

    # When – execute the action under test
    ...

    # Then – assert expected outcomes
    ...

    # Clean – tear down side effects (only if not using fixtures)
    ...
```

- **Given**: Arrange state, create objects, configure mocks, define inputs.
- **When**: Call exactly one function or trigger one action.
- **Then**: Assert outcomes — return values, state changes, side effects.
- **Clean**: Only needed when `yield`-based fixtures can't handle teardown (e.g., globally mutated state). Prefer fixtures for cleanup.

### Language of Phase Comments

Write the phase markers in the language the project already uses for comments and docstrings — do
not force English. Inspect the existing code (and the repository style guide, e.g. `AGENTS.md`)
before choosing: if comments and docstrings are written in Russian, the phases become
`# Дано` / `# Когда` / `# Тогда` / `# Очистка`.

```python
def test_order_placed_when_item_is_in_stock():
    # Дано – зарегистрированный покупатель и товар на складе
    ...

    # Когда – покупатель оформляет заказ
    ...

    # Тогда – заказ подтверждён, остаток на складе уменьшен
    ...
```

Keep a single language for all phase comments within a file; mixing languages is a defect.

---

## Prefer Functions Over Classes

Use **module-level test functions** rather than `TestClass` methods unless grouping is strictly necessary for shared `setup_method` / `teardown_method` logic that cannot be expressed as fixtures.

```python
# ✅ Preferred
def test_user_created_with_valid_data(): ...


# ❌ Avoid unless necessary
class TestUser:
    def test_created_with_valid_data(self): ...
```

Benefits: simpler imports, easier isolation, no accidental shared state via `self`.

---

## Docstrings: Business-Language Specification

**Functional tests must include a docstring** that describes the scenario from the business
point of view — no technical jargon, no mention of mocks, classes, or implementation details.
Unit tests benefit from docstrings but it's not mandatory if the function name is self-explanatory.

```python
def test_order_placed_successfully():
    """
    Given a registered customer with a valid payment method,
    When they place an order for an item that is in stock,
    Then the order is confirmed, the inventory is reduced by one,
    and a confirmation email is sent to the customer.
    """
```

The docstring **mirrors the Given/When/Then comments** but written in plain business language for
stakeholders, in the same language as the rest of the project's comments and docstrings (Russian in
this repository). It becomes living documentation of business rules.

---

## Coverage Requirements

| Test type       | Happy path | All fail branches |
|-----------------|:----------:|:-----------------:|
| Unit            | ✅ required | ✅ required       |
| Functional      | ✅ required | only if asked     |
| Interface       | ✅ required | ✅ required       |
| Integration     | ✅ required | ❌ not required   |

**Every reachable failure branch in the source code must be covered by at least one unit test.**
Functional tests must cover the happy path end-to-end.

---

## Folder Layout

```
tests/
├── conftest.py              # shared fixtures, pytest plugins
├── unit/                    # all external I/O mocked
│   └── conftest.py
├── functional/              # real business logic, 3rd parties NOT mocked*
│   └── conftest.py
├── interface/               # contract tests for exposed API surface
│   └── conftest.py
└── integration/             # nothing mocked, run in dev/staging
    └── conftest.py
```

*Unless the user explicitly requests mocking a specific 3rd-party in functional tests.

Each subfolder has its own `conftest.py` for layer-specific fixtures.

---

## Layer Definitions and Rules

### Unit Tests (`tests/unit/`)

- **Mock ALL external interfaces**: databases, HTTP clients, file I/O, queues, clocks, randomness.
- Test one function or method at a time.
- Fast — no network, no disk, no sleeps.
- Cover: happy path + every `if/elif/else` branch + every exception handler.

```python
# tests/unit/test_payment_service.py
from unittest.mock import MagicMock, patch


def test_charge_succeeds_when_gateway_returns_ok():
    # Given
    gateway = MagicMock()
    gateway.charge.return_value = {"status": "ok", "transaction_id": "txn_123"}
    service = PaymentService(gateway=gateway)

    # When
    result = service.charge(amount=100, currency="USD", token="tok_abc")

    # Then
    assert result.transaction_id == "txn_123"
    gateway.charge.assert_called_once_with(amount=100, currency="USD", token="tok_abc")


def test_charge_raises_when_gateway_declines():
    # Given
    gateway = MagicMock()
    gateway.charge.return_value = {"status": "declined", "reason": "insufficient_funds"}
    service = PaymentService(gateway=gateway)

    # When / Then
    with pytest.raises(PaymentDeclinedError, match="insufficient_funds"):
        service.charge(amount=100, currency="USD", token="tok_abc")
```

### Functional Tests (`tests/functional/`)

- Test complete business flows through real application code.
- Do **not** mock 3rd-party services unless the user explicitly requests it.
- Use a test database, local queues, or in-memory variants as appropriate.
- **Always include a business-language docstring.**
- Cover the happy path; add failure scenarios when explicitly requested.

```python
# tests/functional/test_order_flow.py
def test_order_placed_and_inventory_updated(db_session, email_backend):
    """
    Given a registered customer with a valid payment method and a product with 5 units in stock,
    When the customer places an order for 2 units,
    Then the order status is 'confirmed', the product inventory is reduced to 3,
    and the customer receives an order confirmation email.
    """
    # Given
    customer = CustomerFactory(payment_method="tok_visa")
    product = ProductFactory(stock=5)

    # When
    order = place_order(customer_id=customer.id, product_id=product.id, quantity=2)

    # Then
    assert order.status == "confirmed"
    assert Product.get(product.id).stock == 3
    assert email_backend.outbox[-1].recipient == customer.email
```

### Interface Tests (`tests/interface/`)

- Test the **public contract** of the service: REST endpoints, GraphQL schema, CLI commands.
- Validate: status codes, response schemas, error envelopes, content types, auth requirements.
- Use real HTTP clients against a running app (e.g., FastAPI `TestClient`, Flask `test_client`).
- Do not test internal logic — treat the service as a black box.
- Cover: happy path + all documented error responses (400, 401, 403, 404, 422, 500 contracts).

```python
# tests/interface/test_orders_api.py
def test_create_order_returns_201_with_order_id(client, auth_headers):
    """
    Given a valid order payload and an authenticated user,
    When POST /orders is called,
    Then the response is 201 Created with a JSON body containing an 'order_id'.
    """
    # Given
    payload = {"product_id": "prod_1", "quantity": 1}

    # When
    response = client.post("/orders", json=payload, headers=auth_headers)

    # Then
    assert response.status_code == 201
    assert "order_id" in response.json()


def test_create_order_returns_422_when_quantity_is_zero(client, auth_headers):
    # Given
    payload = {"product_id": "prod_1", "quantity": 0}

    # When
    response = client.post("/orders", json=payload, headers=auth_headers)

    # Then
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(e["loc"] == ["body", "quantity"] for e in errors)
```

### Integration Tests (`tests/integration/`)

- Nothing is mocked — real databases, real 3rd-party APIs, real queues.
- Intended to run in CI against a **dev or staging environment**.
- Typically annotated with `@pytest.mark.integration` so they can be excluded from local runs.
- Focus on happy path and cross-service flows.

```python
# tests/integration/test_payment_gateway.py
import pytest


@pytest.mark.integration
def test_real_charge_succeeds_in_sandbox():
    """
    Given a Stripe sandbox token,
    When a charge is submitted to the real Stripe API,
    Then a transaction ID is returned and the charge appears in the Stripe dashboard.
    """
    # Given
    service = PaymentService()  # uses real Stripe keys from env

    # When
    result = service.charge(amount=50, currency="USD", token="tok_visa")

    # Then
    assert result.transaction_id.startswith("ch_")
```

---

## Fixtures and conftest.py

Layer `conftest.py` files from general (root) to specific (subfolder):

```python
# tests/conftest.py  — shared by all layers
import pytest


@pytest.fixture
def app():
    from myapp import create_app

    return create_app(config="testing")


# tests/unit/conftest.py  — unit-specific
@pytest.fixture
def mock_gateway():
    with patch("myapp.services.payment.StripeGateway") as m:
        yield m.return_value


# tests/functional/conftest.py  — functional-specific
@pytest.fixture
def db_session(app):
    with app.db.begin() as session:
        yield session
        session.rollback()  # Clean


@pytest.fixture
def email_backend():
    from myapp.email import TestEmailBackend

    backend = TestEmailBackend()
    yield backend
    backend.clear()  # Clean
```

Use `yield` fixtures for teardown — the code after `yield` is the **Clean** phase.

---

## Naming Conventions

```
test_<subject>_<outcome>_when_<condition>
test_<subject>_<outcome>_given_<precondition>   # alternative

Examples:
test_charge_succeeds_when_gateway_returns_ok
test_charge_raises_when_card_is_declined
test_create_order_returns_201_with_valid_payload
test_inventory_not_decremented_when_payment_fails
```

---

## Markers and pytest.ini

Define markers in `pytest.ini` or `pyproject.toml`:

```ini
# pytest.ini
[pytest]
markers =
    unit: fast, all mocked
    functional: business flows, real app code
    interface: API contract tests
    integration: nothing mocked, requires external services
```

Run selectively:
```bash
pytest tests/unit/                    # unit only
pytest tests/ -m "not integration"   # skip integration in local dev
pytest tests/ -m integration         # CI staging pipeline
```

---

## Reference Files

- `references/examples/unit/` — annotated unit test examples
- `references/examples/functional/` — annotated functional test examples  
- `references/examples/interface/` — annotated interface test examples
- `references/examples/integration/` — annotated integration test examples

Read the relevant reference when generating tests for a specific layer.
