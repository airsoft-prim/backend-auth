# Functional test examples

Use real business logic and the configured test infrastructure. Do not mock
third-party services unless requested. The example assumes fixtures supply a
real repository and application use case, and clean up their records afterward.
Placeholder types and methods must be adapted to the actual project.

```python
def test_registration_creates_an_active_account(
    register_user: RegisterUser,
    user_repository: UserRepository,
    registration_data: RegistrationData,
) -> None:
    """Create an active account from valid registration data.

    The account is persisted and can be retrieved by its assigned identifier.

    Args:
        register_user (RegisterUser): Registration use case.
        user_repository (UserRepository): Repository backed by the test database.
        registration_data (RegistrationData): Valid registration inputs.
    """
    # Given
    command = registration_data

    # When
    created = register_user.execute(command)

    # Then
    stored = user_repository.get(created.id)
    assert stored is not None
    assert stored.username == command.username
    assert stored.is_active
```

Use `async def` and `await` when the actual interfaces are asynchronous. Describe
only outcomes the test asserts. Do not infer email confirmation, login behavior,
or other features from the example. Functional tests require business-language
Google-style docstrings; localize prose and phase comments to the project.

Keep fixture ownership explicit. A database fixture must isolate changes made by
the application, including commits; a rollback is sufficient only if those writes
participate in the transaction being rolled back. Put cleanup in fixture teardown.
