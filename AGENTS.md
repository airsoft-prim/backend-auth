# AGENTS.md

Working instructions for AI agents in this repository. Treat it as an operating checklist, not
documentation: follow it, keep it short.

## Where to look

| Path                    | Use it for                                           |
| ----------------------- | ---------------------------------------------------- |
| `docs/DOMAIN.md`        | Domain source of truth: entities, policies, roadmap  |
| `docs/API_AUTH.md`      | `/auth` HTTP contract: routes, schemas, status codes |
| `docs/API_PASSWORD.md`  | `/password` HTTP contract: change and reset password |
| `docs/API_HEALTH.md`    | `/health/*` probes: liveness, readiness              |
| `docs/API_WELLKNOWN.md` | `/.well-known/*` contract: JWKS, discovery           |
| `README.md`             | Human-facing showcase: what it is, how to run it     |

Read `docs/DOMAIN.md` and the code the task touches before proposing a solution.

## Scope

- Single source of truth for Airsoft Prim portal users: registration, login, logout; passwords hashed
  with Argon2id (`pwdlib[argon2]`), change and reset; roles `admin` / `moderator` / `user` with block,
  unblock, deactivate, restore; user administration over the API; login audit events.
- Tokens: 24-hour JWT access token signed with EdDSA over Ed25519; public keys published as JWKS at
  `/.well-known/jwks.json` so other services verify tokens locally.
- Policies: password 8-72 characters with a lowercase, an uppercase, a digit and a special character;
  username 3-30 chars of latin letters, digits, `_`, `-`.
- Not implemented and not wanted unprompted: refresh tokens, email confirmation, OAuth2.0 / OIDC
  (discovery document, standard grants, external clients). Do not build them on the side, but do not
  block them either - keep token and route formats compatible with the standard.

## Stack

- Python 3.14 (`requires-python = ">=3.14"`, `.python-version`).
- FastAPI + Uvicorn; Pydantic v2 + pydantic-settings.
- SQLAlchemy 2.0 async + asyncpg, PostgreSQL (schema `auth`), Alembic migrations.
- Redis (`redis.asyncio`), PyJWT, cryptography, pwdlib, aiofiles, Loguru.
- `uv` for packages and environment (`pyproject.toml`, `uv.lock`, `default-groups = "all"`).
- `ruff` for lint and format, `ty` for types, `pytest` for tests.

Dev tooling belongs to `[dependency-groups]` (`dev`, `test`), never to `dependencies`.

## Layout

```text
main.py            entry point: uvicorn + app from src
src/app.py         FastAPI assembly, lifespan
src/api/           HTTP layer: auth/, health/, password/, well_known/
src/core/          cross-cutting config (configs/) and logging
src/services/      domain services: JWT, JWKS
src/general/       shared types and enums
src/providers/     external resources: database/ (engine, models, repositories), cache/
migrations/        Alembic
tests/             pytest
docs/              project documentation
```

Dependency direction: `api` -> `services` -> (`providers`, `core`) -> `general`.
Routers never reach the database directly: data access goes through `providers/repositories/`, domain
logic through `services/`; providers know nothing about HTTP. Attach a new router to `main_router` in
`src/api/__init__.py`.

## Commands

```bash
uv sync                  # environment (default-groups = "all": dev + test)
uv run python main.py    # service on http://localhost:8000
uv run ruff check .      # lint
uv run ruff format .     # format
uv run ty check          # types
uv run pytest            # tests
uv run pytest -n auto    # parallel (pytest-xdist)
uv run pytest --cov      # with coverage

# migrations: the database URL comes from ALEMBIC_URI
ALEMBIC_URI="postgresql+asyncpg://user:pass@localhost:5432/db" uv run alembic upgrade head
ALEMBIC_URI="postgresql+asyncpg://user:pass@localhost:5432/db" uv run alembic revision --autogenerate -m "add something"
```

Configuration comes from the environment with prefixes `APP_`, `CACHE_`, `DATABASE_`;
`APP_DEBUG=true` enables debug and auto-reload. Secrets never enter the repository (`.env` is ignored).

Readiness, database and cache work, and migrations need real PostgreSQL and Redis. Without them, say
exactly what stayed unverified instead of reporting a green run as verified.

## Code style

Source of truth is `ruff.toml` and `ty.toml`, not this section. Expect `line-length = 100`,
`target-version = "py314"`, double quotes, and rule sets `C90, N, UP, S, BLE, B, C4, DTZ, EM, FA, ISC,
PIE, PT, SLF, SIM, ARG, ERA, A, F, Q, ASYNC, E, W, T20, ANN, PL, RET, RUF, PYI, PD`.

- Annotate everything, return types included (`ANN`).
- No `print` (`T20`): log through `loguru.logger`.
- `assert` only in tests (`S101` off for `tests/**`); application code checks explicitly.
- No commented-out code (`ERA`).
- Timezone-aware datetimes only (`DTZ`): `DateTime(timezone=True)` in models, `datetime.now(UTC)` in code.
- Exception text goes to a variable first (`EM`): `msg = "Invalid database name."; raise ValueError(msg)`.
- No builtin shadowing (`A`), no other objects' private attributes (`SLF`), shallow branching (`SIM`,
  `RET`, `C90`, `max-complexity = 10`).
- Russian is fine in strings and docstrings (`RUF001` / `RUF002` are off); error and exception messages
  stay English because they reach API responses and logs.
- Google-style docstrings (`Args` / `Returns` / `Yields`), Russian allowed.
- `src/core/configs/*` attributes are `UPPER_CASE` and mirror env variable names; wrapper properties
  need `# noqa: N802` (see `CacheConfiguration.DSN`).
- One sorted import list (`force-sort-within-sections`), with `combine-as-imports`.
- New public module members go to `__all__` (see `src/__init__.py`, `src/api/__init__.py`).
- OpenAPI descriptions live in `docs.py` next to the router, typed with `RouteDocs` (pattern:
  `src/api/health/docs.py`).
- Pad markdown tables to equal widths in every `.md` file, this one included; realign a whole table
  block when editing it.

Reference patterns: `src/api/health/routes.py`, `src/core/configs/database.py`,
`src/providers/database/models.py`. Before finishing, run `uv run ruff check .`, `uv run ruff format .`,
`uv run ty check`.

## Tests

- `pytest.ini`: `testpaths = tests`, `python_files = test_*.py`, `asyncio_mode = auto` (no decorator for
  async tests), console logging at DEBUG. Fixtures in `tests/conftest.py`.
- Cover what is expensive to get wrong: JWT / JWKS services, configuration validation, database and
  cache access, endpoint behavior (status codes, payload shapes).
- A test needing real PostgreSQL or Redis fails or skips loudly; never pass just because infrastructure
  is missing.

## Comments and docs

- Comment non-obvious decisions, invariants and constraints; a comment that restates the code is noise
  (tone reference: `NAMING_CONVENTION` in `src/providers/database/models.py`).
- In service and config files (`ruff.toml`, `ty.toml`, `pyproject.toml`, `pytest.ini`, `alembic.ini`) edit
  without comments: explanations there are the project owner's job. Markdown docs do need explanations.
- `README.md` stays a compact showcase; update `docs/DOMAIN.md` when domain logic changes.

## Git

- Conventional Commits with a layer or module scope: `feat(api): ...`, `fix(config): ...`,
  `chore(deps): ...`; imperative English subject, as in existing history.
- One commit is one coherent change; no mixed commits.
- Main branch is `main`. New branches, commits and `push` only on an explicit request.

## Forbidden without an explicit request

- Hand-editing the database schema. Tables, columns, indexes and enums change only through Alembic
  migrations in `migrations/` (autogenerated from `BaseModel.metadata`); no manual database edits, no
  edits to applied migrations.
- Editing other repositories (`backend-api`, `backend-media`, `frontend`).
- Adding dependencies or modifying `pyproject.toml` / `uv.lock`.
- Changing public contracts: endpoint URLs, request and response formats, env variable names.
- Weakening security: logging secrets, passwords or tokens; disabling or bypassing checks; committing
  signing keys, `.env` or other secrets.
- Refactoring, renaming or "improving" anything outside the task.
- Extending the service towards OAuth2 / OIDC.

## Workflow

1. Read the domain and the relevant code, then propose a solution.
2. Make the smallest coherent change, following the layering and conventions above.
3. Verify: `uv run ruff check .`, `uv run ruff format .`, `uv run ty check`, `uv run pytest`.
4. Report what changed and what was actually verified; state plainly what could not be checked.
