# Integration test examples

Run against configured real test/dev/staging infrastructure without mocks. The
example assumes a real database repository and an existing marker registration.
Placeholder interfaces must be adapted to the implementation.

```python
import pytest


@pytest.mark.integration
async def test_saved_user_can_be_retrieved(
    user_repository: UserRepository,
    new_user: User,
) -> None:
    """Retrieve a persisted user from the test database.

    Args:
        user_repository (UserRepository): Repository backed by real PostgreSQL.
        new_user (User): Unique user whose record is cleaned up by its fixture.
    """
    # Given
    repository = user_repository

    # When
    await repository.save(new_user)
    retrieved = await repository.get(new_user.id)

    # Then
    assert retrieved is not None
    assert retrieved.id == new_user.id
    assert retrieved.username == new_user.username
```

Fixtures must release connections and remove or roll back test records even when
assertions fail. A missing database/cache must fail or skip visibly. Do not replace
it with a double and still report the test as integration verification.

For queue or background-work checks, use bounded polling with a deadline rather
than unbounded waits. Register cleanup as soon as a resource is created, so a
failed assertion cannot bypass it.

Select this layer with `uv run pytest -m integration`. Use
`uv run pytest -m "not integration"` when intentionally excluding it; other layers
may still need infrastructure. Reuse the project's registered marker and async
settings rather than copying new configuration from an example.
