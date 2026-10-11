# Unit Test Examples

Unit tests mock ALL external interfaces and test one unit of logic at a time.
Every reachable branch — happy path and failures — must be covered.

---

## Example: Service with repository and external API

```python
# tests/unit/test_user_service.py
import pytest
from unittest.mock import MagicMock, patch, call
from myapp.services.user import UserService
from myapp.exceptions import UserNotFoundError, DuplicateEmailError


# ── Happy path ──────────────────────────────────────────────────────────────


def test_create_user_returns_new_user_with_generated_id():
    # Given
    repo = MagicMock()
    repo.save.return_value = {"id": "usr_1", "email": "alice@example.com", "name": "Alice"}
    mailer = MagicMock()
    service = UserService(repo=repo, mailer=mailer)

    # When
    user = service.create(email="alice@example.com", name="Alice")

    # Then
    assert user.id == "usr_1"
    assert user.email == "alice@example.com"
    repo.save.assert_called_once()


def test_create_user_sends_welcome_email():
    # Given
    repo = MagicMock()
    repo.save.return_value = {"id": "usr_1", "email": "alice@example.com", "name": "Alice"}
    mailer = MagicMock()
    service = UserService(repo=repo, mailer=mailer)

    # When
    service.create(email="alice@example.com", name="Alice")

    # Then
    mailer.send_welcome.assert_called_once_with(to="alice@example.com", name="Alice")


def test_get_user_returns_existing_user():
    # Given
    repo = MagicMock()
    repo.find_by_id.return_value = {"id": "usr_1", "email": "alice@example.com"}
    service = UserService(repo=repo, mailer=MagicMock())

    # When
    user = service.get("usr_1")

    # Then
    assert user.id == "usr_1"
    repo.find_by_id.assert_called_once_with("usr_1")


# ── Failure branches ─────────────────────────────────────────────────────────


def test_create_user_raises_when_email_already_exists():
    # Given
    repo = MagicMock()
    repo.save.side_effect = DuplicateEmailError("alice@example.com")
    service = UserService(repo=repo, mailer=MagicMock())

    # When / Then
    with pytest.raises(DuplicateEmailError, match="alice@example.com"):
        service.create(email="alice@example.com", name="Alice")


def test_create_user_does_not_send_email_when_save_fails():
    # Given
    repo = MagicMock()
    repo.save.side_effect = Exception("DB error")
    mailer = MagicMock()
    service = UserService(repo=repo, mailer=mailer)

    # When / Then
    with pytest.raises(Exception):
        service.create(email="alice@example.com", name="Alice")

    mailer.send_welcome.assert_not_called()


def test_get_user_raises_when_not_found():
    # Given
    repo = MagicMock()
    repo.find_by_id.return_value = None
    service = UserService(repo=repo, mailer=MagicMock())

    # When / Then
    with pytest.raises(UserNotFoundError, match="usr_999"):
        service.get("usr_999")
```

---

## Example: Patching at the import site

When the code under test imports directly (e.g., `from myapp.clients import stripe`),
patch at the **import site**, not at the definition site.

```python
def test_charge_calls_stripe_with_correct_params():
    # Given
    with patch("myapp.services.payment.stripe") as mock_stripe:
        mock_stripe.Charge.create.return_value = MagicMock(id="ch_123")
        service = PaymentService()

        # When
        result = service.charge(amount=500, currency="usd", token="tok_visa")

    # Then
    assert result.transaction_id == "ch_123"
    mock_stripe.Charge.create.assert_called_once_with(amount=500, currency="usd", source="tok_visa")
```

---

## Example: Time and randomness

Always mock non-deterministic sources.

```python
from unittest.mock import patch
import datetime


def test_token_includes_current_timestamp():
    # Given
    fixed_time = datetime.datetime(2024, 1, 15, 12, 0, 0)
    with patch("myapp.auth.datetime") as mock_dt:
        mock_dt.utcnow.return_value = fixed_time
        service = TokenService()

        # When
        token = service.generate(user_id="usr_1")

    # Then
    assert token.expires_at == fixed_time + datetime.timedelta(hours=1)
```

---

## conftest.py for unit layer

```python
# tests/unit/conftest.py
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_user_repo():
    return MagicMock()


@pytest.fixture
def mock_mailer():
    return MagicMock()


@pytest.fixture
def user_service(mock_user_repo, mock_mailer):
    from myapp.services.user import UserService

    return UserService(repo=mock_user_repo, mailer=mock_mailer)
```
