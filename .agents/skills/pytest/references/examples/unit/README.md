# Unit test examples

Adapt placeholder services and ports to the code under test. Examples are structural
snippets; use project annotations and the predominant documentation language.

## Isolated failure and side effect

```python
from unittest.mock import MagicMock

import pytest


def test_create_user_does_not_notify_when_save_fails() -> None:
    # Given
    repository = MagicMock()
    repository.save.side_effect = DuplicateUserError("User already exists.")
    notifier = MagicMock()
    service = UserService(repository=repository, notifier=notifier)

    # When / Then
    with pytest.raises(DuplicateUserError, match="User already exists"):
        service.create(username="alice")

    notifier.send.assert_not_called()
```

Use the actual exception raised by the implementation. For awaited collaborators,
use `AsyncMock` and assertions such as `assert_awaited_once_with`.

## Patch at the lookup site

```python
from datetime import UTC, datetime
from unittest.mock import patch


def test_token_records_the_current_time() -> None:
    # Given
    fixed_time = datetime(2026, 1, 1, tzinfo=UTC)
    with patch("myapp.tokens.current_time", return_value=fixed_time):
        # When
        token = issue_token(user_id="user-1")

    # Then
    assert token.issued_at == fixed_time
```

Patch the name resolved by `issue_token`, not an unrelated definition of the same
helper. Control randomness through the same principle. Cover success, each
reachable failure branch, and exception handlers without invoking real I/O.
