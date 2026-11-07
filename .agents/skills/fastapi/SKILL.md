---
name: fastapi
description: >-
  Implement and review FastAPI endpoints, routers, Pydantic v2 schemas, dependency
  injection, OpenAPI documentation, and application lifespan using project conventions.
  Use for changes to the HTTP application surface, not unrelated backend logic.
---

# FastAPI

Apply these project conventions to FastAPI and Pydantic v2 code. Follow the
repository's architecture and installed Python/framework versions; do not treat
these style choices as limitations of FastAPI or permission to redesign contracts.
Examples use placeholder application and feature names. Read only the reference
relevant to the task; snippets illustrate shapes, not complete standalone modules.

## Routers and path operations

- Declare one `APIRouter` per URL prefix with one human-readable tag. Declare the
  prefix and tag once; endpoint paths contain only the remaining URL segment.
- Use `""` for the collection and `"/{identifier}"` for a member. Paths have no
  trailing slash. Put version prefixes on routers or their inclusion point once.
- Keep `summary`, `description`, `status_code`, `dependencies`, and `responses`
  at the operation level. Aggregate feature routers in the main router and attach
  it to the application once.
- Use fully annotated `async def` handlers named `<verb>_<subject>`; probes use
  `<subject>_healthcheck`. Delegate business behavior to injected collaborators.
  Keep storage access and business branching outside ordinary handlers; boundary
  error translation and probes may require transport-specific branching.
- Apply documentation with `@router.post("", **CREATE_ORDER_DOCS)`. Use the return
  annotation as the response model; do not duplicate it with `response_model=`.
  Use a concrete response model rather than an unstructured `dict` or `Any`.
  This is a project convention: annotated dictionaries can still produce schemas.
- Use `Annotated[T, Depends(...)]`, `Annotated[int, Path(ge=1)]`, and similar
  parameter markers. Defaults belong to request values, not dependency declarations.
- Model structured request bodies with Pydantic. Keep scalar path and query
  parameters explicit when they express the contract clearly.
- Use `-> None` for no result; use an explicit framework response for non-JSON
  payloads or status-only probes. Set explicit response statuses with
  `fastapi.status` constants and preserve empty bodies for 204 responses.
- Include request objects, background tasks, or clients only when needed. For an
  explicitly requested contract stub, retain its signature and raise
  `NotImplementedError`; do not leave stubs in an implementation task.

Read [routers](references/examples/routers.md) for aggregation and versioning,
and [endpoints](references/examples/endpoint.md) for handler shapes and stubs.

## OpenAPI and documentation

- Keep one `<ACTION>_DOCS` constant per operation in its documentation module.
  Reuse the project's `RouteDocs` typed dictionary, with optional keys and no
  `response_model`. Do not duplicate it per feature.
- Write a one-sentence summary ending with a period. Describe actual behavior,
  side effects, and material limitations precisely. Spell out `deprecated`.
- Use `fastapi.status` constants for success codes and documented failures.
  Include `operation_id` and `response_description` only when useful.
- Keep HTTP statuses and client-visible error responses in OpenAPI documentation.
  Python docstrings follow [python-docstrings](../python-docstrings/SKILL.md),
  including its language, concision, types, and directly-raised-exception rules.
  Use the predominant project documentation language for OpenAPI text and field
  descriptions. Logs and exception messages remain English.

Read [documentation as data](references/examples/docs-as-data.md) when changing
operation metadata or its shared type.

## Schemas

- Use Pydantic v2 models for request and response contracts. Give every field a
  description and add examples when the value is not self-evident.
- Name request bodies `<Action>RequestBody`; name responses for their meaning.
- Use `SecretStr` for secret values, enums for closed vocabularies, and
  timezone-aware timestamp types or validation. Plain `datetime` alone does not
  enforce timezone awareness.
- Share reusable validation through `Annotated` aliases and `AfterValidator`;
  pair `@field_validator` with `@classmethod`. Do not copy shared policies.
- Use discriminated unions for polymorphic payloads and
  `ConfigDict(from_attributes=True)` when constructing models from object attributes.
- Express input validation in schemas rather than duplicating it in handlers.

Read [schemas](references/examples/schemas.md) for aliases, model fields, and unions.

## Dependencies and resource ownership

- Let FastAPI resolve dependencies; do not call dependency providers manually in
  handlers. Request caching is enabled by default, not a guarantee that nested
  dependencies have no cost.
- Own scoped resources with generator dependencies and context managers. Match
  acquisition and cleanup, including exceptional exits. Cleanup timing depends
  on dependency scope; do not assume every yield dependency closes at one fixed
  point in response delivery.
- Use named targets in dependency factories. Keep provider identities stable and
  importable for `app.dependency_overrides`; retain a factory's returned callable
  when it must be overridden.
- Do not use `app.state` as a registry for request-scoped dependencies. Reuse a
  cached settings instance rather than reparsing configuration per endpoint.

Read [dependencies](references/examples/dependencies.md) for ownership, factories,
and isolated test overrides.

## Lifespan and application assembly

- Use an async context manager passed as `FastAPI(lifespan=lifespan)` rather than
  startup/shutdown event decorators. Annotate the generator and use `_` for an
  unused application parameter.
- Start long-running work at startup; stop the work owned by that lifespan during
  teardown. Use `try/finally` when cleanup must run after exceptions at `yield`.
- Reuse process-level pools and clients through existing project factories and
  composition roots. Do not force import-time connections or relocate ownership
  merely to match an example. Each worker has its own lifespan.
- Log startup, completion, and shutdown with the project's logger and severity
  conventions (`info`, `success`, `warning` here), naming the component in English.
- Preserve application metadata, documentation URL configuration, middleware,
  handlers, and router wiring. Add configuration only when the task requires it.
- Use an import string for reload or multiple worker processes. An app object is
  suitable for an existing single-process launch without reload.

Read [lifespan and app](references/examples/lifespan-and-app.md) for assembly.

## Errors and verification

- Use 201 for creation, 200 for returned results, and 204 for successful empty
  responses where the existing contract calls for them. Let FastAPI handle
  ordinary validation failures and unsupported methods.
- Raise `HTTPException` at the HTTP boundary or use shared exception handlers.
  Inner layers raise domain/application exceptions. Document expected HTTP error
  responses even when produced by dependencies or shared handlers; the narrower
  Python `Raises:` rule does not limit OpenAPI error documentation.
- Broad catches are reserved for boundaries such as readiness probes that must
  return a controlled status. Mark them for the linter and log the failure;
  never silently swallow it. Use empty probe responses and keep details in logs.
- Build English exception messages in a variable before raising. Use the project
  logger rather than `print`.
- Exercise changed endpoints through the ASGI application to check routing,
  validation, serialization, statuses, and error mapping. Reuse the project's
  HTTP/ASGI test client and restore dependency overrides in fixture teardown.
- Confirm `app.openapi()` builds after schema or metadata changes. Run relevant
  tests and repository checks; state when infrastructure prevented verification.

Read [errors and probes](references/examples/errors-and-probes.md) for boundary
translation and health responses.
