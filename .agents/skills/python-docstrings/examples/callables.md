# Callables examples

These English snippets illustrate documentation structure. Adapt placeholder types
and claims to the implementation and use the project documentation language.

## Generator values

```python
from collections.abc import Iterator


def iter_names(names: list[str]) -> Iterator[str]:
    """Yield names with surrounding whitespace removed.

    Args:
        names (list[str]): Names in the order to emit them.

    Yields:
        str: Next name with surrounding whitespace removed.
    """
    for name in names:
        yield name.strip()
```

## Constructor

```python
def __init__(self, a: int) -> None:
    """Initialize the class.

    Args:
        a (int): Argument A.
    """
    ...
```

## Protected method

```python
def _get_process_name(self, pid: int) -> str:
    """Get a process name by its ID."""
    ...
```

## Property

```python
@property
def is_active(self) -> bool:
    """Whether the user is active."""
    return self._is_active
```

## Class method

```python
@classmethod
def from_config(cls, config: DatabaseConfig) -> Self:
    """Create a client from database configuration.

    Args:
        config (DatabaseConfig): Database connection settings.

    Returns:
        Self: Client using the supplied connection settings.
    """
    return cls(dsn=config.dsn)
```

## Static method

```python
@staticmethod
def normalize_username(username: str) -> str:
    """Strip surrounding whitespace and lowercase the username.

    Args:
        username (str): Original username.

    Returns:
        str: Normalized username.
    """
    return username.strip().lower()
```

## Overloads

```python
from typing import overload


@overload
def find_user(identifier: int) -> User | None: ...


@overload
def find_user(identifier: str) -> User | None: ...


def find_user(identifier: int | str) -> User | None:
    """Find a user by ID or username.

    Args:
        identifier (int | str): Numeric ID or username.

    Returns:
        User | None: Matching user, or `None` if no record matches.
    """
    ...
```

## Public callable

```python
def connect_to_next_port(self, minimum: int) -> int:
    """Return the next available port at or above the lower bound.

    Validate the minimum port and search for the nearest open port starting
    at that value.

    Args:
        minimum (int): Minimum port number, at least `1024`.

    Returns:
        int: The available port number.

    Raises:
        ValueError: If `minimum` is below `1024`.
        ConnectionError: If no available port is found.
    """
    ...
```
