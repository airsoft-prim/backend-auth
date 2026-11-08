# Packages examples

These English snippets illustrate documentation structure. Adapt placeholder types
and claims to the implementation and use the project documentation language.

## Package responsibilities

```python
# adapters/database/repositories/__init__.py
"""PostgreSQL implementations of repository ports.

Loads and persists domain entities through asynchronous database sessions.

Connects application use cases to PostgreSQL through the repository interfaces
defined by the domain layer.
"""
```
