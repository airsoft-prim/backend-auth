---
name: pytest
description: >-
  Write, extend, and review pytest suites using Given/When/Then/Clean, isolated
  fixtures, and unit, functional, interface, and integration test layers. Use for
  test implementation, coverage work, fixture design, and pytest configuration.
---

# Pytest

Use tests as executable specifications of observable behavior. Read the changed
code, existing tests, fixtures, and pytest configuration before choosing a layer.
Preserve the repository's test organization and dependencies; examples do not
require new frameworks, folders, or infrastructure unrelated to the task.

## Structure and naming

- Prefer module-level test functions. Use test classes only when necessary shared
  setup/teardown cannot be expressed cleanly with fixtures.
- Name tests `test_<subject>_<outcome>_when_<condition>` or
  `test_<subject>_<outcome>_given_<precondition>`.
- Follow Given / When / Then / Clean: establish preconditions, perform one logical
  action, assert outcomes, and release resources. A business flow may contain
  several calls when those calls constitute the scenario being tested.
- Use explicit phase comments in the project's comment language, consistently
  within a file. For Russian, use `Дано`, `Когда`, `Тогда`, and `Очистка`.
  Combine When/Then when `pytest.raises` encloses the action.
- Prefer fixture teardown for Clean. Keep necessary inline cleanup exception-safe
  with context managers or `try/finally`, not only after assertions.
- Assert results, state changes, and required side effects. Check collaborator
  calls when the interaction is part of the behavior, not merely an implementation
  detail. Match specific exceptions and stable error details.

## Documentation

Functional tests require a concise business-language docstring describing the
scenario and expected outcome without mock or implementation details. Unit test
docstrings are optional when names are self-explanatory.

Follow [python-docstrings](../python-docstrings/SKILL.md) for Google Style,
project language, and editorial conventions. Put the summary on the opening line;
add scenario detail only when it provides information beyond the summary. Do not
copy phase comments verbatim into prose. Fixture parameters are documented with
types where applicable under the shared callable rules.

## Layers and coverage

Apply the coverage expectations to the code and behavior under test; do not expand
an ordinary scoped change into a rewrite of the entire suite.

| Layer       | Happy path | Failure coverage                        | External boundaries                       |
| ----------- | ---------- | --------------------------------------- | ----------------------------------------- |
| Unit        | Required   | Every reachable failure branch          | Mock or control all external interfaces   |
| Functional  | Required   | Additional scenarios when requested     | Real application flow; see rules below    |
| Interface   | Required   | All documented error-response contracts | Exercise the exposed application boundary |
| Integration | Required   | Not mandatory                           | Real infrastructure; no mocks             |

### Unit: `tests/unit/`

Test one unit of logic. Mock external I/O and control clocks and randomness.
Use no network, real file I/O, or sleeps. Cover reachable condition branches and
exception handlers. Patch names where the code under test looks them up; use
async-aware doubles for awaited collaborators.

Read [unit examples](references/examples/unit/README.md) for patches and failures.

### Functional: `tests/functional/`

Exercise complete business flows through real application logic. Do not mock
third-party services unless explicitly requested. Use test infrastructure or
supported local/in-memory implementations where suitable; state which boundaries
are real and which are substituted. Do not present an in-memory double as proof
of compatibility with an external service.

Read [functional examples](references/examples/functional/README.md) for scenarios.

### Interface: `tests/interface/`

Exercise the public contract through its actual boundary. For HTTP, use an HTTP
or ASGI client against the application rather than calling handlers directly.
Check status, schema, content type, authentication, authorization, and documented
error responses. Assert only the statuses the actual contract defines.

Read [interface examples](references/examples/interface/README.md) for ASGI checks.

### Integration: `tests/integration/`

Use real databases, caches, queues, and applicable external services without mocks.
Use configured test/dev/staging environments. Mark tests `integration` so runs can
select them. Cover cross-component happy paths; failure coverage is optional.
Missing infrastructure must fail or skip visibly, never yield a false green check.

Read [integration examples](references/examples/integration/README.md) for setup.

## Fixtures and configuration

- Put common fixtures in root `conftest.py` and layer-specific fixtures in the
  appropriate subfolder. Create files only when they contain needed fixtures.
- Use scopes that preserve isolation. Release sessions, clients, transactions,
  files, and background work; restore patches and dependency overrides on failure.
  Ensure cleanup registration survives partial setup failures.
- Use isolated test records or rollback strategies appropriate to the actual
  transaction boundaries. Rolling back a different session does not undo a
  committed application transaction.
- Reuse installed clients and plugins. Do not add dependencies or change pytest
  configuration unless the task calls for it. Register new markers if used.
- Follow existing async settings. This repository uses `asyncio_mode = auto`,
  so async tests do not need an `asyncio` marker.

## Verification

Run the affected layer or targeted cases first, then required repository checks.
Use `uv run pytest tests/unit/` or the relevant path. Select integration tests with
`uv run pytest -m integration`; exclude them with `-m "not integration"` only
when appropriate. Excluding integration does not guarantee all remaining tests
are infrastructure-free.

Report what ran, what passed or failed, and any skips or unavailable infrastructure.
Do not claim that mocks verify the external system they replace.
