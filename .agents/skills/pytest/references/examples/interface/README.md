# Interface test examples

Exercise the application through the existing HTTP/ASGI client. These snippets use
placeholder client and fixture types; adapt paths, payloads, and status expectations
to the actual API contract. They do not require a new HTTP client dependency.

```python
def test_create_order_returns_201_with_an_identifier(
    client: ASGIClient,
    auth_headers: dict[str, str],
) -> None:
    # Given
    payload = {"product_id": "product-1", "quantity": 2}

    # When
    response = client.post("/orders", json=payload, headers=auth_headers)

    # Then
    assert response.status_code == 201
    assert isinstance(response.json()["order_id"], str)


def test_create_order_returns_422_when_quantity_is_zero(
    client: ASGIClient,
    auth_headers: dict[str, str],
) -> None:
    # Given
    payload = {"product_id": "product-1", "quantity": 0}

    # When
    response = client.post("/orders", json=payload, headers=auth_headers)

    # Then
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(error["loc"] == ["body", "quantity"] for error in errors)
```

Add cases for authentication, authorization, missing resources, and other error
responses only as defined by the actual contract. Check error envelopes and content
types as well as codes where relevant. Keep internal collaborator assertions in
unit tests. Restore dependency overrides in fixture teardown, even on assertion
failure. If a test relies on startup resources, ensure its harness runs lifespan.
