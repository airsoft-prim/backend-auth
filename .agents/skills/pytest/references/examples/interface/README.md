# Interface Test Examples

Interface tests validate the public contract of the service from the outside.
The service is treated as a black box — only HTTP responses, schemas, and status
codes are asserted. No internal logic is tested here.

---

## Example: REST API contract tests (FastAPI)

```python
# tests/interface/test_orders_api.py
import pytest
from fastapi.testclient import TestClient
from myapp.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    response = client.post("/auth/token", json={"email": "test@example.com", "password": "secret"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Happy path ───────────────────────────────────────────────────────────────


def test_create_order_returns_201_with_order_id(client, auth_headers):
    """
    Given an authenticated user and a valid order payload,
    When POST /orders is called,
    Then the response is 201 Created with a JSON body that includes an 'order_id'.
    """
    # Given
    payload = {"product_id": "prod_abc", "quantity": 2}

    # When
    response = client.post("/orders", json=payload, headers=auth_headers)

    # Then
    assert response.status_code == 201
    body = response.json()
    assert "order_id" in body
    assert isinstance(body["order_id"], str)


def test_get_order_returns_200_with_full_schema(client, auth_headers, existing_order_id):
    # Given / When
    response = client.get(f"/orders/{existing_order_id}", headers=auth_headers)

    # Then
    assert response.status_code == 200
    body = response.json()
    assert "order_id" in body
    assert "status" in body
    assert "total_cents" in body
    assert "created_at" in body


# ── Auth failures ─────────────────────────────────────────────────────────────


def test_create_order_returns_401_without_token(client):
    # Given
    payload = {"product_id": "prod_abc", "quantity": 1}

    # When
    response = client.post("/orders", json=payload)

    # Then
    assert response.status_code == 401


def test_get_order_returns_403_when_accessing_another_users_order(
    client, auth_headers_other_user, existing_order_id
):
    # When
    response = client.get(f"/orders/{existing_order_id}", headers=auth_headers_other_user)

    # Then
    assert response.status_code == 403


# ── Validation failures ───────────────────────────────────────────────────────


def test_create_order_returns_422_when_quantity_is_zero(client, auth_headers):
    # Given
    payload = {"product_id": "prod_abc", "quantity": 0}

    # When
    response = client.post("/orders", json=payload, headers=auth_headers)

    # Then
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(e["loc"] == ["body", "quantity"] for e in errors)


def test_create_order_returns_422_when_product_id_is_missing(client, auth_headers):
    # Given
    payload = {"quantity": 1}  # missing product_id

    # When
    response = client.post("/orders", json=payload, headers=auth_headers)

    # Then
    assert response.status_code == 422


def test_get_order_returns_404_when_order_does_not_exist(client, auth_headers):
    # When
    response = client.get("/orders/nonexistent-id", headers=auth_headers)

    # Then
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
```

---

## Example: REST API contract tests (Flask)

```python
# tests/interface/test_users_api.py
import pytest
import json


def test_register_user_returns_201_with_location_header(client):
    """
    Given a valid registration payload,
    When POST /users is called,
    Then the response is 201 Created with a Location header pointing to the new user resource.
    """
    # Given
    payload = {"name": "Alice", "email": "alice@example.com", "password": "P@ssw0rd!"}

    # When
    response = client.post("/users", data=json.dumps(payload), content_type="application/json")

    # Then
    assert response.status_code == 201
    assert "Location" in response.headers
    assert response.headers["Location"].startswith("/users/")


def test_register_user_returns_409_when_email_already_taken(client, existing_user):
    # Given
    payload = {"name": "Alice 2", "email": existing_user.email, "password": "P@ssw0rd!"}

    # When
    response = client.post("/users", data=json.dumps(payload), content_type="application/json")

    # Then
    assert response.status_code == 409
    assert response.json["error_code"] == "EMAIL_ALREADY_EXISTS"
```

---

## Example: GraphQL contract tests

```python
# tests/interface/test_graphql_schema.py

PLACE_ORDER_MUTATION = """
mutation PlaceOrder($productId: ID!, $quantity: Int!) {
  placeOrder(productId: $productId, quantity: $quantity) {
    orderId
    status
    totalCents
  }
}
"""


def test_place_order_mutation_returns_order_fields(graphql_client, auth_headers):
    """
    Given a valid product and authenticated user,
    When the placeOrder mutation is called,
    Then the response includes orderId, status, and totalCents.
    """
    # Given
    variables = {"productId": "prod_1", "quantity": 1}

    # When
    response = graphql_client.post(
        "/graphql",
        json={"query": PLACE_ORDER_MUTATION, "variables": variables},
        headers=auth_headers,
    )

    # Then
    assert response.status_code == 200
    data = response.json()["data"]["placeOrder"]
    assert data["orderId"] is not None
    assert data["status"] == "CONFIRMED"
    assert isinstance(data["totalCents"], int)


def test_place_order_returns_graphql_error_when_unauthenticated(graphql_client):
    # Given
    variables = {"productId": "prod_1", "quantity": 1}

    # When
    response = graphql_client.post(
        "/graphql", json={"query": PLACE_ORDER_MUTATION, "variables": variables}
    )

    # Then
    assert response.status_code == 200  # GraphQL always 200
    errors = response.json().get("errors", [])
    assert any("unauthenticated" in e["message"].lower() for e in errors)
```

---

## conftest.py for interface layer

```python
# tests/interface/conftest.py
import pytest
from myapp.main import app as flask_app


@pytest.fixture(scope="session")
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers(client):
    resp = client.post("/auth/login", json={"email": "itest@example.com", "password": "secret"})
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def existing_order_id(client, auth_headers):
    resp = client.post(
        "/orders",
        json={"product_id": "prod_seed_1", "quantity": 1},
        headers=auth_headers,
    )
    return resp.get_json()["order_id"]
```
