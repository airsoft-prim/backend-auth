# Functional Test Examples

Functional tests exercise complete business flows through the real application code.
Third-party services are NOT mocked unless the user explicitly requests it.
Every test must include a business-language docstring.

---

## Example: Order placement flow

```python
# tests/functional/test_order_flow.py
import pytest
from myapp.use_cases import place_order, cancel_order
from myapp.models import Order, Product, Customer
from tests.factories import CustomerFactory, ProductFactory


def test_customer_can_place_order_for_in_stock_product(db_session):
    """
    Given a registered customer with a valid payment method
    and a product with 5 units available in stock,
    When the customer places an order for 2 units,
    Then the order is confirmed, the product stock decreases to 3,
    and the customer's order history includes the new order.
    """
    # Given
    customer = CustomerFactory(payment_token="tok_visa", db=db_session)
    product = ProductFactory(stock=5, price=2999, db=db_session)

    # When
    order = place_order(
        customer_id=customer.id,
        product_id=product.id,
        quantity=2,
        db=db_session,
    )

    # Then
    assert order.status == "confirmed"
    assert order.total_cents == 5998

    refreshed_product = db_session.get(Product, product.id)
    assert refreshed_product.stock == 3

    customer_orders = db_session.query(Order).filter_by(customer_id=customer.id).all()
    assert any(o.id == order.id for o in customer_orders)


def test_order_is_rejected_when_product_is_out_of_stock(db_session):
    """
    Given a product that has no units left in stock,
    When a customer attempts to place an order for that product,
    Then the order is not created and the customer receives an
    'out of stock' error message.
    """
    # Given
    customer = CustomerFactory(payment_token="tok_visa", db=db_session)
    product = ProductFactory(stock=0, db=db_session)

    # When / Then
    with pytest.raises(OutOfStockError):
        place_order(customer_id=customer.id, product_id=product.id, quantity=1, db=db_session)

    order_count = db_session.query(Order).filter_by(customer_id=customer.id).count()
    assert order_count == 0


def test_cancelled_order_restores_stock(db_session):
    """
    Given a confirmed order for 2 units of a product that now has 3 units in stock,
    When the customer cancels the order,
    Then the order status changes to 'cancelled' and the product stock returns to 5.
    """
    # Given
    product = ProductFactory(stock=5, db=db_session)
    customer = CustomerFactory(db=db_session)
    order = place_order(customer_id=customer.id, product_id=product.id, quantity=2, db=db_session)
    assert db_session.get(Product, product.id).stock == 3  # pre-condition check

    # When
    cancel_order(order_id=order.id, db=db_session)

    # Then
    assert db_session.get(Order, order.id).status == "cancelled"
    assert db_session.get(Product, product.id).stock == 5
```

---

## Example: User registration flow

```python
# tests/functional/test_user_registration.py


def test_new_user_can_register_and_log_in(db_session, email_backend):
    """
    Given a new visitor who has never registered before,
    When they submit a valid registration form with their name, email, and password,
    Then an account is created, a verification email is sent to their inbox,
    and after verifying, they can log in with their credentials.
    """
    # Given
    registration_data = {
        "name": "Bob Smith",
        "email": "bob@example.com",
        "password": "S3cure!Pass",
    }

    # When
    user = register_user(**registration_data, db=db_session)

    # Then – account created
    assert user.id is not None
    assert user.is_verified is False

    # Then – verification email sent
    assert len(email_backend.outbox) == 1
    verification_email = email_backend.outbox[0]
    assert verification_email.to == "bob@example.com"
    assert "verify" in verification_email.subject.lower()

    # When – user verifies email
    token = extract_verification_token(verification_email.body)
    verify_email(token=token, db=db_session)

    # Then – user can log in
    session = login(email="bob@example.com", password="S3cure!Pass", db=db_session)
    assert session.user_id == user.id
```

---

## conftest.py for functional layer

```python
# tests/functional/conftest.py
import pytest
from myapp import create_app
from myapp.database import get_engine


@pytest.fixture(scope="session")
def app():
    return create_app(config="testing")


@pytest.fixture
def db_session(app):
    """Provide a transactional DB session that rolls back after each test."""
    engine = get_engine(app.config["DATABASE_URL"])
    connection = engine.connect()
    transaction = connection.begin()
    session = app.db.session(bind=connection)

    yield session

    session.close()
    transaction.rollback()  # Clean
    connection.close()


@pytest.fixture
def email_backend():
    """In-memory email backend that captures sent emails."""
    from myapp.email import TestEmailBackend

    backend = TestEmailBackend()
    with patch("myapp.email.backend", backend):
        yield backend
    backend.clear()  # Clean
```
