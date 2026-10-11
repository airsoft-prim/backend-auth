# Integration Test Examples

Integration tests run against real infrastructure — real databases, real third-party APIs,
real queues. Nothing is mocked. These tests are meant for dev/staging CI pipelines.

Mark all integration tests with `@pytest.mark.integration` so they can be excluded
from local development runs.

---

## Example: Real payment gateway

```python
# tests/integration/test_stripe_payment.py
import pytest
import os


@pytest.mark.integration
def test_stripe_charge_succeeds_with_sandbox_token():
    """
    Given the Stripe sandbox environment and a test card token,
    When a charge is submitted through the PaymentService,
    Then Stripe returns a real transaction ID and the charge is recorded.
    """
    # Given
    service = PaymentService()  # reads STRIPE_SECRET_KEY from env

    # When
    result = service.charge(amount=100, currency="usd", token="tok_visa")

    # Then
    assert result.transaction_id.startswith("ch_")
    assert result.amount == 100


@pytest.mark.integration
def test_stripe_charge_fails_with_declined_card_token():
    """
    Given a test token that simulates a declined card,
    When a charge is attempted,
    Then a PaymentDeclinedError is raised with the decline reason from Stripe.
    """
    # Given
    service = PaymentService()

    # When / Then
    with pytest.raises(PaymentDeclinedError) as exc_info:
        service.charge(amount=100, currency="usd", token="tok_chargeDeclined")

    assert "insufficient_funds" in str(exc_info.value).lower()
```

---

## Example: Real database and cache

```python
# tests/integration/test_product_repository.py
import pytest


@pytest.mark.integration
def test_product_is_saved_and_retrievable_from_real_db(pg_session):
    """
    Given a PostgreSQL database in the test environment,
    When a product is created and then fetched by ID,
    Then the retrieved product matches the saved data exactly.
    """
    # Given
    repo = ProductRepository(db=pg_session)
    product_data = {"name": "Widget Pro", "price_cents": 4999, "stock": 100}

    # When
    saved = repo.create(**product_data)
    retrieved = repo.get(saved.id)

    # Then
    assert retrieved.id == saved.id
    assert retrieved.name == "Widget Pro"
    assert retrieved.price_cents == 4999


@pytest.mark.integration
def test_product_stock_update_is_reflected_in_cache(pg_session, redis_client):
    """
    Given a product stored in the database and cached in Redis,
    When the product's stock is updated,
    Then the cached value is invalidated so subsequent reads reflect the new stock.
    """
    # Given
    repo = ProductRepository(db=pg_session, cache=redis_client)
    product = repo.create(name="Gadget", price_cents=1999, stock=10)
    _ = repo.get(product.id)  # populate cache

    # When
    repo.update_stock(product.id, new_stock=7)

    # Then
    cached = redis_client.get(f"product:{product.id}")
    assert cached is None  # cache must be invalidated

    fresh = repo.get(product.id)
    assert fresh.stock == 7
```

---

## Example: Cross-service flow

```python
# tests/integration/test_order_fulfillment_pipeline.py
import pytest
import time


@pytest.mark.integration
def test_order_triggers_warehouse_notification_via_queue(
    db_session, sqs_client, warehouse_queue_url
):
    """
    Given a confirmed order in the database,
    When the order fulfillment pipeline processes the order,
    Then a warehouse notification message appears in the SQS queue
    within 5 seconds, containing the correct order details.
    """
    # Given
    order = create_confirmed_order(db=db_session)

    # When
    trigger_fulfillment_pipeline(order_id=order.id)

    # Then – poll queue with timeout
    deadline = time.time() + 5
    messages = []
    while time.time() < deadline and not messages:
        response = sqs_client.receive_message(QueueUrl=warehouse_queue_url, MaxNumberOfMessages=1)
        messages = response.get("Messages", [])
        if not messages:
            time.sleep(0.5)

    assert len(messages) == 1
    body = json.loads(messages[0]["Body"])
    assert body["order_id"] == str(order.id)
    assert body["event"] == "ORDER_READY_FOR_FULFILLMENT"

    # Clean
    sqs_client.delete_message(
        QueueUrl=warehouse_queue_url, ReceiptHandle=messages[0]["ReceiptHandle"]
    )
```

---

## conftest.py for integration layer

```python
# tests/integration/conftest.py
import pytest
import os
import psycopg2
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import boto3
import redis


@pytest.fixture(scope="session")
def pg_engine():
    url = os.environ["TEST_DATABASE_URL"]  # e.g. postgresql://user:pass@staging-db/testdb
    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def pg_session(pg_engine):
    Session = sessionmaker(bind=pg_engine)
    session = Session()
    yield session
    session.rollback()  # Clean
    session.close()


@pytest.fixture(scope="session")
def redis_client():
    return redis.Redis.from_url(os.environ["TEST_REDIS_URL"])


@pytest.fixture(scope="session")
def sqs_client():
    return boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "us-east-1"))
```

---

## pytest.ini / pyproject.toml marker registration

```ini
# pytest.ini
[pytest]
markers =
    integration: marks tests that require real external services (deselect with '-m "not integration"')
```

Run integration tests only in CI:

```bash
# Local development — skip integration
pytest tests/ -m "not integration"

# CI staging pipeline — run all including integration
pytest tests/ -m integration --tb=short
```
