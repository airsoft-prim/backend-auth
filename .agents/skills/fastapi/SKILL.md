---
name: fastapi
description: >
  How to write FastAPI code, portable across projects: routers and prefixes, path operations,
  request and response models, Depends-based dependency injection, OpenAPI documentation kept as
  data, lifespan and the application object, status codes and error reporting. Use this skill
  whenever the user asks to add, change or review an endpoint, a router, a dependency, an APIRouter,
  a request/response schema, Swagger descriptions, a health probe or the lifespan of a FastAPI
  application. Also trigger on mentions of "APIRouter", "Depends", "dependency_overrides",
  "response_model", "lifespan", "route docs", "swagger", "openapi.json" or "healthcheck".
---

# FastAPI Style

Rules for writing FastAPI code that hold in any project. It assumes FastAPI plus Pydantic v2 and
covers the framework surface only: routers, path operations, schemas, dependencies, OpenAPI,
lifespan, statuses. Project architecture — packages, layers, how storage is reached — is out of
scope.

`myapp` is a placeholder package, `orders` a placeholder feature, `RouteDocs`, `OrderService`,
`get_session` placeholder roles: keep the shapes, use the names of the project you are in. Snippets
assume Python 3.13+ typing (PEP 695 `type` aliases, the optional second parameter of
`AsyncGenerator`). Annotated examples: `references/examples/`.

## Routers

- One `APIRouter` per URL prefix: `router = APIRouter(prefix="/orders", tags=["Orders"])`.
- `prefix` and a single human-readable tag are declared once, on the router. Endpoints add neither,
  and never repeat the prefix in their own path.
- No `summary`, `description`, `status_code`, `dependencies=` or `responses=` on the router: those
  belong to a path operation, so a reader finds them where they apply.
- A path never ends with a slash: `@router.post("")` is the collection under the prefix,
  `@router.get("/{order_id}")` a member. Depending on the trailing-slash redirect costs a round trip
  and breaks clients that refuse redirects.
- If the API is versioned, the version is part of the `prefix`, not of a path or a decorator.
- Routers are gathered into one main router and attached to the application once with
  `include_router`. The application object is the only place that decides what is exposed.

See `references/examples/routers.md`.

## Path Operations

- `async def`, with every parameter and the return value annotated.
- Name `<verb>_<subject>` (`create_order`); liveness-style probes are `<subject>_healthcheck`.
- The decorator carries the method, the path and the spread documentation:
  `@router.post("", **CREATE_ORDER_DOCS)`.
- The return annotation **is** the response model. `response_model=` is never passed, because two
  declarations of one contract drift apart. `-> None` for an endpoint with no body, and the success
  code then comes from the documentation constant.
- Parameters are annotated, including parameter markers:
  `service: Annotated[OrderService, Depends(get_order_service)]`,
  `order_id: Annotated[int, Path(ge=1)]`, `page: Annotated[int, Query(ge=1)] = 1`. The
  `x: T = Depends(...)` form is never used.
- Request data arrives as models, not as a `dict` or a bag of loose query values. A `dict` return
  silently drops the response model from the OpenAPI document.
- A response that is not JSON is an explicit framework response built in the handler with a status
  constant: `PlainTextResponse(status_code=status.HTTP_204_NO_CONTENT)`.
- The request object, background tasks and storage clients stay out of the signature unless the
  endpoint genuinely needs them. A handler delegates to its injected collaborators instead of doing
  their work, and holds no branching over transport concerns.
- Docstring: Google style with `Args` / `Returns` / `Raises`; the type is repeated in parentheses
  under `Args`; statuses belong to the documentation module, not to the docstring.
- Human-facing text — docstrings, OpenAPI text, field descriptions — is written in the team's
  language; log and exception messages are always English. One file never mixes the two roles.

An endpoint whose interface is final and whose behavior is not written yet keeps the whole contract
and ends with `raise NotImplementedError`; an undecided dependency is annotated `Any` with its
meaning described in the docstring.

See `references/examples/endpoint.md`.

## OpenAPI Documentation as Data

- Documentation is data, applied by spreading it into the decorator: one `<ACTION>_DOCS` constant
  per path operation.
- The shared shape is a `TypedDict` declared once (for example `RouteDocs`) that mirrors the path
  operation's keyword arguments and never contains `response_model`. Being `total=False`, it keeps
  optional keys optional.
- `summary` is one sentence ending with a period; `description` states behavior and side effects and
  admits what is not implemented yet.
- Codes are `fastapi.status` constants, never bare integers; `deprecated` is always spelled out;
  failures the transport must report go under `responses`.
- `operation_id` and `response_description` appear only where they carry something.

See `references/examples/docs-as-data.md`.

## Schemas

- Pydantic v2 models are the single contract for bodies and responses: a `Field(...)` description on
  every field, and `examples=[...]` where the value is not self-evident.
- Secrets are `SecretStr`, closed vocabularies are enums, timestamps are timezone-aware.
- A validation rule shared by more than one model is an `Annotated` alias (with `AfterValidator`),
  never a copied validator; a `@field_validator` is paired with `@classmethod`.
- Request bodies are named `<Action>RequestBody`; responses are named for what they mean.
- Polymorphic payloads use a discriminated union, so the schema shows the alternatives instead of a
  shapeless object. Models built from arbitrary objects set `ConfigDict(from_attributes=True)`.
- Validation failures are the framework's job: let the model raise and answer 422. An endpoint does
  not pre-validate what a schema can already express.

See `references/examples/schemas.md`.

## Dependencies

- Dependencies are declared with `Annotated[T, Depends(...)]` and never called by hand in the body.
  FastAPI resolves a dependency once per request and reuses the result, so nesting them is free.
- A dependency that owns a connection is a generator: `async with ... as client: yield client`, so
  the framework closes it when the request ends, exceptions included. Cleanup goes after that
  `yield`.
- A dependency that must target something specific is built by a factory and named at the call site:
  `Depends(get_client(Shard.REPORTS))` — a named member instead of a magic number or a connection
  string.
- Dependency callables stay module-level and importable, so `app.dependency_overrides` can replace
  them by identity in tests, and the tests clear the overrides afterwards.
- `app.state` is not a dependency registry: a dependency either builds a cheap object or yields a
  scoped resource.
- Settings are not injected per route: one cached instance is shared.

See `references/examples/dependencies.md`.

## Lifespan and the Application Object

- `@asynccontextmanager async def lifespan(_: FastAPI) -> AsyncGenerator[None]`, passed as
  `FastAPI(lifespan=lifespan)`. The application argument is unnamed unless the lifespan genuinely
  reads it, and the yield type is `None`.
- Startup starts long-running background work; teardown after `yield` stops exactly that work and
  nothing else. The lifespan replaces the deprecated `@app.on_event("startup")` pair.
- Pools and clients that live for the whole process are created once, not per request and not inside
  the lifespan's startup body.
- Phase boundaries are logged — `info` on entry, `success` on completion, `warning` before
  shutdown — with English messages that name the component.
- The application object carries `title`, `description`, `version`, `lifespan` and its routers. It
  keeps FastAPI's defaults for `/docs`, `/redoc` and `/openapi.json`; middleware, exception handlers
  and `tags_metadata` are added only when they earn their place.
- Serving the app: uvicorn with the import string and `reload=True` while developing, with the app
  object itself in production. Each worker process runs its own lifespan, so startup work must not
  assume a single instance.

See `references/examples/lifespan-and-app.md`.

## Status Codes and Errors

- Codes are chosen once per path operation and documented there: 201 for a created resource, 200 for
  a returned one, 204 with an empty body when there is nothing to return.
- 422 for a validation failure and 405 for a wrong method come from the framework. They are never
  hand-built.
- Transport-level failures are raised at the boundary: `HTTPException` in the handler, or one
  `@application.exception_handler` when many endpoints share the same mapping. Code that knows
  nothing about HTTP raises its own error types instead.
- A failure the client must be able to handle is declared under `responses` in the documentation
  constant, so Swagger and reality agree. A handler registered for an error type without that entry
  makes the documentation lie.
- A handler that must always answer — a probe is the canonical case — catches broadly, marks the
  catch the way the project's linter requires (`# noqa: BLE001` under ruff), logs the reason at a
  severity that stands out and returns an explicit status. A broad catch is the exception, never the
  norm, and never swallows silently.
- Exception messages are English and built into a variable before being raised:
  `msg = "Order not found."; raise ValueError(msg)`. `print` is never used; logging goes through the
  project's logger.

See `references/examples/errors-and-probes.md`.

## Verifying a FastAPI Change

- Exercise endpoints through the ASGI app, not by calling handlers directly: routing, validation,
  response serialization and error handling are part of what you are checking.
- If the project has no HTTP test client, drive the ASGI app with a small helper instead of adding a
  dependency.
- `app.dependency_overrides` plus clearing them in a teardown fixture is the seam for substituting
  collaborators.
- After changing descriptions or schemas, confirm `app.openapi()` still builds.

## Style Archetypes

Shapes to compare FastAPI code against while writing or reviewing it.

- **Thin Route** — a path operation that declares a contract and delegates; no branching, no storage
  calls, no `try` in the body.
- **Docs-as-Data** — one `<ACTION>_DOCS` constant per operation, spread into the decorator with
  `**`.
- **Scoped Dependency** — a generator dependency: `async with` around a `yield`, closed with the
  request.
- **Idle Lifespan** — one factory call on startup, phase logs, teardown only for what was started.
- **Probe Endpoint** — a bare status and no body, a marked broad `except`, a critical log naming the
  component that failed.
- **Contract Stub** — final signature and docs, body `raise NotImplementedError`.

## Reference Examples

- `references/examples/routers.md` — router declaration, tags, aggregation with `include_router`.
- `references/examples/endpoint.md` — path operations, parameters, a contract stub.
- `references/examples/docs-as-data.md` — the shared documentation shape and route constants.
- `references/examples/schemas.md` — request and response models, shared policies, unions.
- `references/examples/dependencies.md` — `Depends`, generator dependencies, test overrides.
- `references/examples/lifespan-and-app.md` — lifespan, the application object, serving the app.
- `references/examples/errors-and-probes.md` — status codes, `HTTPException`, a probe handler.
